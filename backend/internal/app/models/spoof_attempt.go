package models

import "time"

type SpoofAttempt struct {
	ID             int64
	IDNumberHash   string
	PredictedClass string
	Confidence     float64
	ImagePath      *string
	Decision       string
	CreatedAt      time.Time
}
