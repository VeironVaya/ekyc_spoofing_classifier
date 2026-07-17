package dtos

// RegisterPreviewResponse mirrors RegisterResponse but omits Decision - a
// preview never saves anything or reaches a final decision, it only runs the
// checks so the user can review/correct the extracted fields before confirming.
type RegisterPreviewResponse struct {
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
}
