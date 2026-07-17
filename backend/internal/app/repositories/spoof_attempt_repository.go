package repositories

import (
	"database/sql"

	"ekyc-backend/internal/app/models"
)

type SpoofAttemptRepository struct {
	DB *sql.DB
}

func NewSpoofAttemptRepository(db *sql.DB) *SpoofAttemptRepository {
	return &SpoofAttemptRepository{DB: db}
}

func (r *SpoofAttemptRepository) LogAttempt(attempt *models.SpoofAttempt) (int64, error) {
	result, err := r.DB.Exec(
		`INSERT INTO spoof_attempts (id_number_hash, predicted_class, confidence, image_path, decision) VALUES (?, ?, ?, ?, ?)`,
		attempt.IDNumberHash, attempt.PredictedClass, attempt.Confidence, attempt.ImagePath, attempt.Decision,
	)
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

// GetPriorAttempts returns the attempt history for a hashed ID number, most
// recent first. Call this before LogAttempt for the current attempt so the
// history reflects what came strictly before it.
func (r *SpoofAttemptRepository) GetPriorAttempts(idNumberHash string) ([]models.SpoofAttempt, error) {
	rows, err := r.DB.Query(
		`SELECT id, id_number_hash, predicted_class, confidence, image_path, decision, created_at
		 FROM spoof_attempts WHERE id_number_hash = ? ORDER BY created_at DESC`,
		idNumberHash,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var attempts []models.SpoofAttempt
	for rows.Next() {
		var a models.SpoofAttempt
		if err := rows.Scan(&a.ID, &a.IDNumberHash, &a.PredictedClass, &a.Confidence, &a.ImagePath, &a.Decision, &a.CreatedAt); err != nil {
			return nil, err
		}
		attempts = append(attempts, a)
	}
	return attempts, rows.Err()
}

func (r *SpoofAttemptRepository) GetByID(id int64) (*models.SpoofAttempt, error) {
	var a models.SpoofAttempt
	err := r.DB.QueryRow(
		`SELECT id, id_number_hash, predicted_class, confidence, image_path, decision, created_at
		 FROM spoof_attempts WHERE id = ?`,
		id,
	).Scan(&a.ID, &a.IDNumberHash, &a.PredictedClass, &a.Confidence, &a.ImagePath, &a.Decision, &a.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// GetAllAttempts returns attempts across all users, most recent first, for
// the admin dashboard.
func (r *SpoofAttemptRepository) GetAllAttempts(limit, offset int) ([]models.SpoofAttempt, error) {
	rows, err := r.DB.Query(
		`SELECT id, id_number_hash, predicted_class, confidence, image_path, decision, created_at
		 FROM spoof_attempts ORDER BY created_at DESC LIMIT ? OFFSET ?`,
		limit, offset,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var attempts []models.SpoofAttempt
	for rows.Next() {
		var a models.SpoofAttempt
		if err := rows.Scan(&a.ID, &a.IDNumberHash, &a.PredictedClass, &a.Confidence, &a.ImagePath, &a.Decision, &a.CreatedAt); err != nil {
			return nil, err
		}
		attempts = append(attempts, a)
	}
	return attempts, rows.Err()
}
