package dtos

import "time"

// AttemptResponse is the admin-dashboard view of a logged attempt. It
// deliberately omits the raw filesystem image_path - evidence images are
// only ever fetched through the auth-gated image route.
type AttemptResponse struct {
	ID              int64     `json:"id"`
	IDNumberHash    string    `json:"id_number_hash"`
	PredictedClass  string    `json:"predicted_class"`
	Confidence      float64   `json:"confidence"`
	IsLive          bool      `json:"is_live"`
	Decision        string    `json:"decision"`
	HasImage        bool      `json:"has_image"`
	BlurScore       *float64  `json:"blur_score,omitempty"`
	BrightnessScore *float64  `json:"brightness_score,omitempty"`
	CreatedAt       time.Time `json:"created_at"`
}
