package services

import "ekyc-backend/internal/app/models"

type Decision string

const (
	DecisionContinue Decision = "continue_registration"
	DecisionReview   Decision = "manual_review"
	DecisionBlocked  Decision = "blocked_flagged"
)

// blockThreshold is the number of prior spoof attempts for the same hashed
// ID required before a new spoof attempt escalates to blocked_flagged.
// Deliberately graduated - a single flagged attempt is never an instant
// permanent ban.
const blockThreshold = 3

type DecisionService struct{}

func NewDecisionService() *DecisionService {
	return &DecisionService{}
}

func (d *DecisionService) Decide(predictedClass string, priorAttempts []models.SpoofAttempt) Decision {
	priorSpoofCount := 0
	for _, a := range priorAttempts {
		if a.PredictedClass != "realperson" {
			priorSpoofCount++
		}
	}

	isSpoof := predictedClass != "realperson"

	switch {
	case !isSpoof && priorSpoofCount >= blockThreshold:
		// Genuine this time, but risky history - still worth a human look.
		return DecisionReview
	case !isSpoof:
		return DecisionContinue
	case priorSpoofCount >= blockThreshold:
		return DecisionBlocked
	default:
		return DecisionReview
	}
}
