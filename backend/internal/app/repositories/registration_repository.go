package repositories

import (
	"database/sql"

	"ekyc-backend/internal/app/models"
)

type RegistrationRepository struct {
	DB *sql.DB
}

func NewRegistrationRepository(db *sql.DB) *RegistrationRepository {
	return &RegistrationRepository{DB: db}
}

func (r *RegistrationRepository) LogRegistration(reg *models.Registration) (int64, error) {
	result, err := r.DB.Exec(
		`INSERT INTO registrations
		 (nik_hash, extracted_name, extracted_dob, liveness_predicted_class, liveness_confidence,
		  face_match_verified, face_match_distance, id_card_image_path, selfie_image_path, decision, automated_decision,
		  id_card_blur_score, id_card_brightness_score, selfie_blur_score, selfie_brightness_score)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		reg.NIKHash, reg.ExtractedName, reg.ExtractedDOB, reg.LivenessPredictedClass, reg.LivenessConfidence,
		reg.FaceMatchVerified, reg.FaceMatchDistance, reg.IDCardImagePath, reg.SelfieImagePath, reg.Decision, reg.AutomatedDecision,
		reg.IDCardBlurScore, reg.IDCardBrightnessScore, reg.SelfieBlurScore, reg.SelfieBrightnessScore,
	)
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func (r *RegistrationRepository) GetAllRegistrations(limit, offset int) ([]models.Registration, error) {
	rows, err := r.DB.Query(
		`SELECT id, nik_hash, extracted_name, extracted_dob, liveness_predicted_class, liveness_confidence,
		        face_match_verified, face_match_distance, id_card_image_path, selfie_image_path, decision, automated_decision,
		        id_card_blur_score, id_card_brightness_score, selfie_blur_score, selfie_brightness_score, created_at
		 FROM registrations ORDER BY created_at DESC LIMIT ? OFFSET ?`,
		limit, offset,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var regs []models.Registration
	for rows.Next() {
		var reg models.Registration
		if err := rows.Scan(&reg.ID, &reg.NIKHash, &reg.ExtractedName, &reg.ExtractedDOB, &reg.LivenessPredictedClass,
			&reg.LivenessConfidence, &reg.FaceMatchVerified, &reg.FaceMatchDistance, &reg.IDCardImagePath,
			&reg.SelfieImagePath, &reg.Decision, &reg.AutomatedDecision,
			&reg.IDCardBlurScore, &reg.IDCardBrightnessScore, &reg.SelfieBlurScore, &reg.SelfieBrightnessScore,
			&reg.CreatedAt); err != nil {
			return nil, err
		}
		regs = append(regs, reg)
	}
	return regs, rows.Err()
}

func (r *RegistrationRepository) UpdateDecision(id int64, decision string) error {
	result, err := r.DB.Exec(`UPDATE registrations SET decision = ? WHERE id = ?`, decision, id)
	if err != nil {
		return err
	}
	rows, err := result.RowsAffected()
	if err != nil {
		return err
	}
	if rows == 0 {
		return sql.ErrNoRows
	}
	return nil
}

func (r *RegistrationRepository) GetByID(id int64) (*models.Registration, error) {
	var reg models.Registration
	err := r.DB.QueryRow(
		`SELECT id, nik_hash, extracted_name, extracted_dob, liveness_predicted_class, liveness_confidence,
		        face_match_verified, face_match_distance, id_card_image_path, selfie_image_path, decision, automated_decision,
		        id_card_blur_score, id_card_brightness_score, selfie_blur_score, selfie_brightness_score, created_at
		 FROM registrations WHERE id = ?`,
		id,
	).Scan(&reg.ID, &reg.NIKHash, &reg.ExtractedName, &reg.ExtractedDOB, &reg.LivenessPredictedClass,
		&reg.LivenessConfidence, &reg.FaceMatchVerified, &reg.FaceMatchDistance, &reg.IDCardImagePath,
		&reg.SelfieImagePath, &reg.Decision, &reg.AutomatedDecision,
		&reg.IDCardBlurScore, &reg.IDCardBrightnessScore, &reg.SelfieBlurScore, &reg.SelfieBrightnessScore,
		&reg.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &reg, nil
}
