package dtos

import "time"

// RegistrationResponse is the admin-dashboard view of a logged registration.
// Like AttemptResponse, it omits raw filesystem paths - images are only
// fetched through the auth-gated image route.
type RegistrationResponse struct {
	ID                     int64     `json:"id"`
	NIKHash                string    `json:"nik_hash,omitempty"`
	ExtractedName          string    `json:"extracted_name,omitempty"`
	ExtractedDOB           string    `json:"extracted_dob,omitempty"`
	LivenessPredictedClass string    `json:"liveness_predicted_class"`
	LivenessConfidence     float64   `json:"liveness_confidence"`
	FaceMatchVerified      bool      `json:"face_match_verified"`
	FaceMatchDistance      *float64  `json:"face_match_distance,omitempty"`
	Decision               string    `json:"decision"`
	AutomatedDecision      string    `json:"automated_decision,omitempty"`
	IDCardBlurScore        *float64  `json:"id_card_blur_score,omitempty"`
	IDCardBrightnessScore  *float64  `json:"id_card_brightness_score,omitempty"`
	SelfieBlurScore        *float64  `json:"selfie_blur_score,omitempty"`
	SelfieBrightnessScore  *float64  `json:"selfie_brightness_score,omitempty"`
	HasIDCardImage         bool      `json:"has_id_card_image"`
	HasSelfieImage         bool      `json:"has_selfie_image"`
	CreatedAt              time.Time `json:"created_at"`
}
