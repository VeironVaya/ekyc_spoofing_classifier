package models

import "time"

type SpoofAttempt struct {
	ID              int64
	IDNumberHash    string
	PredictedClass  string
	Confidence      float64
	ImagePath       *string
	Decision        string
	BlurScore       *float64
	BrightnessScore *float64
	CreatedAt       time.Time
}
