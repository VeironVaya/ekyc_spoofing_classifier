package config

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

func ConnectDB(cfg *Config) (*sql.DB, error) {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true&charset=utf8mb4",
		cfg.DBUser, cfg.DBPassword, cfg.DBHost, cfg.DBPort, cfg.DBName)

	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}

	// The mysql container may still be starting when this runs, so retry
	// instead of failing on the first connection attempt.
	var pingErr error
	for i := 0; i < 15; i++ {
		pingErr = db.Ping()
		if pingErr == nil {
			break
		}
		log.Printf("database not ready yet, retrying (%d/15): %v", i+1, pingErr)
		time.Sleep(2 * time.Second)
	}
	if pingErr != nil {
		return nil, fmt.Errorf("could not connect to database: %w", pingErr)
	}

	if err := migrate(db); err != nil {
		return nil, err
	}

	return db, nil
}

func migrate(db *sql.DB) error {
	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS spoof_attempts (
			id BIGINT AUTO_INCREMENT PRIMARY KEY,
			id_number_hash CHAR(64) NOT NULL,
			predicted_class VARCHAR(32) NOT NULL,
			confidence DOUBLE NOT NULL,
			image_path VARCHAR(255) NULL,
			decision VARCHAR(32) NOT NULL DEFAULT '',
			created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			INDEX idx_id_number_hash (id_number_hash)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
	`); err != nil {
		return err
	}

	// Covers tables created before the decision column existed. MySQL has no
	// ADD COLUMN IF NOT EXISTS, so check information_schema first.
	if err := addDecisionColumnIfMissing(db); err != nil {
		return err
	}

	_, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS registrations (
			id BIGINT AUTO_INCREMENT PRIMARY KEY,
			nik_hash CHAR(64) NULL,
			extracted_name VARCHAR(255) NULL,
			extracted_dob VARCHAR(32) NULL,
			liveness_predicted_class VARCHAR(32) NOT NULL,
			liveness_confidence DOUBLE NOT NULL,
			face_match_verified BOOLEAN NOT NULL,
			face_match_distance DOUBLE NULL,
			id_card_image_path VARCHAR(255) NULL,
			selfie_image_path VARCHAR(255) NULL,
			decision VARCHAR(32) NOT NULL,
			created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			INDEX idx_nik_hash (nik_hash)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
	`)
	return err
}

func addDecisionColumnIfMissing(db *sql.DB) error {
	var count int
	err := db.QueryRow(`
		SELECT COUNT(*) FROM information_schema.COLUMNS
		WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spoof_attempts' AND COLUMN_NAME = 'decision'
	`).Scan(&count)
	if err != nil {
		return err
	}
	if count > 0 {
		return nil
	}

	_, err = db.Exec(`ALTER TABLE spoof_attempts ADD COLUMN decision VARCHAR(32) NOT NULL DEFAULT ''`)
	return err
}
