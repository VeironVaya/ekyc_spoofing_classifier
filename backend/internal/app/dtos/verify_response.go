package dtos

type VerifyResponse struct {
	PredictedClass      string             `json:"predicted_class"`
	Confidence          float64            `json:"confidence"`
	IsLive              bool               `json:"is_live"`
	AllScores           map[string]float64 `json:"all_scores"`
	Decision            string             `json:"decision"`
	QualityPassed       bool               `json:"quality_passed"`
	QualityRejectReason *string            `json:"quality_reject_reason,omitempty"`
}
