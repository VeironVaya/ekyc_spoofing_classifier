package dtos

import "mime/multipart"

type KtpForgeryRequest struct {
	File      *multipart.FileHeader `form:"file" binding:"required"`
	MockClass string                `form:"mock_class"`
}

type KtpForgeryResponse struct {
	PredictedClass      string             `json:"predicted_class"`
	Confidence          float64            `json:"confidence"`
	IsAuthentic         bool               `json:"is_authentic"`
	AllScores           map[string]float64 `json:"all_scores"`
	IsDummy             bool               `json:"is_dummy"`
	BlurScore           float64            `json:"blur_score"`
	BrightnessScore     float64            `json:"brightness_score"`
	QualityPassed       bool               `json:"quality_passed"`
	QualityRejectReason *string            `json:"quality_reject_reason,omitempty"`
}

type PipelinePreviewRequest struct {
	IDCard       *multipart.FileHeader `form:"id_card" binding:"required"`
	Selfie       *multipart.FileHeader `form:"selfie" binding:"required"`
	MockKtpClass string                `form:"mock_ktp_class"`
}

type PipelinePreviewResponse struct {
	ExtractedNIK           string              `json:"extracted_nik,omitempty"`
	ExtractedName          string              `json:"extracted_name,omitempty"`
	ExtractedDOB           string              `json:"extracted_dob,omitempty"`
	RawOCRText             string              `json:"raw_ocr_text"`
	LivenessPredictedClass string              `json:"liveness_predicted_class"`
	LivenessConfidence     float64             `json:"liveness_confidence"`
	IsLive                 bool                `json:"is_live"`
	FaceMatchVerified      bool                `json:"face_match_verified"`
	FaceMatchDistance      *float64            `json:"face_match_distance,omitempty"`
	FaceMatchError         string              `json:"face_match_error,omitempty"`
	KtpForgery             *KtpForgeryResponse `json:"ktp_forgery,omitempty"`
	QualityPassed          bool                `json:"quality_passed"`
	QualityRejectReason    *string             `json:"quality_reject_reason,omitempty"`
}

