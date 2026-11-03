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
			blur_score DOUBLE NULL,
			brightness_score DOUBLE NULL,
			created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			INDEX idx_id_number_hash (id_number_hash)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
	`); err != nil {
		return err
	}

	// Covers tables created before these columns existed. MySQL has no ADD
	// COLUMN IF NOT EXISTS, so check information_schema first.
	if err := addColumnIfMissing(db, "spoof_attempts", "decision", "VARCHAR(32) NOT NULL DEFAULT ''"); err != nil {
		return err
	}
	if err := addColumnIfMissing(db, "spoof_attempts", "blur_score", "DOUBLE NULL"); err != nil {
		return err
	}
	if err := addColumnIfMissing(db, "spoof_attempts", "brightness_score", "DOUBLE NULL"); err != nil {
		return err
	}

	if _, err := db.Exec(`
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
			automated_decision VARCHAR(32) NULL,
			id_card_blur_score DOUBLE NULL,
			id_card_brightness_score DOUBLE NULL,
			selfie_blur_score DOUBLE NULL,
			selfie_brightness_score DOUBLE NULL,
			created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			INDEX idx_nik_hash (nik_hash)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
	`); err != nil {
		return err
	}

	if err := addColumnIfMissing(db, "registrations", "automated_decision", "VARCHAR(32) NULL"); err != nil {
		return err
	}
	if err := addColumnIfMissing(db, "registrations", "id_card_blur_score", "DOUBLE NULL"); err != nil {
		return err
	}
	if err := addColumnIfMissing(db, "registrations", "id_card_brightness_score", "DOUBLE NULL"); err != nil {
		return err
	}
	if err := addColumnIfMissing(db, "registrations", "selfie_blur_score", "DOUBLE NULL"); err != nil {
		return err
	}
	if err := addColumnIfMissing(db, "registrations", "selfie_brightness_score", "DOUBLE NULL"); err != nil {
		return err
	}

	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS api_requests (
			id BIGINT AUTO_INCREMENT PRIMARY KEY,
			method VARCHAR(8) NOT NULL,
			route VARCHAR(128) NOT NULL,
			status_code INT NOT NULL,
			duration_ms DOUBLE NOT NULL,
			created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			INDEX idx_route_created_at (route, created_at)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
	`); err != nil {
		return err
	}

	return nil
}

func addColumnIfMissing(db *sql.DB, table, column, definition string) error {
	var count int
	err := db.QueryRow(`
		SELECT COUNT(*) FROM information_schema.COLUMNS
		WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?
	`, table, column).Scan(&count)
	if err != nil {
		return err
	}
	if count > 0 {
		return nil
	}

	_, err = db.Exec(fmt.Sprintf(`ALTER TABLE %s ADD COLUMN %s %s`, table, column, definition))
	return err
}
