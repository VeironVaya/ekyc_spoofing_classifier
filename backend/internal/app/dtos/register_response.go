package dtos

type RegisterResponse struct {
	ExtractedNIK           string   `json:"extracted_nik,omitempty"`
	ExtractedName          string   `json:"extracted_name,omitempty"`
	ExtractedDOB           string   `json:"extracted_dob,omitempty"`
	RawOCRText             string   `json:"raw_ocr_text"`
	LivenessPredictedClass string   `json:"liveness_predicted_class"`
	LivenessConfidence     float64  `json:"liveness_confidence"`
	IsLive                 bool     `json:"is_live"`
	FaceMatchVerified      bool     `json:"face_match_verified"`
	FaceMatchDistance      *float64 `json:"face_match_distance,omitempty"`
	FaceMatchError         string   `json:"face_match_error,omitempty"`
	Decision               string   `json:"decision"`
	QualityPassed          bool     `json:"quality_passed"`
	QualityRejectReason    *string  `json:"quality_reject_reason,omitempty"`
}
