package models

import "time"

type Registration struct {
	ID                     int64
	NIKHash                *string
	ExtractedName          *string
	ExtractedDOB           *string
	LivenessPredictedClass string
	LivenessConfidence     float64
	FaceMatchVerified      bool
	FaceMatchDistance      *float64
	IDCardImagePath        *string
	SelfieImagePath        *string
	Decision               string
	AutomatedDecision      *string
	IDCardBlurScore        *float64
	IDCardBrightnessScore  *float64
	SelfieBlurScore        *float64
	SelfieBrightnessScore  *float64
	CreatedAt              time.Time
}
