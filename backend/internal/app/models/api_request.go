package models

import "time"

type APIRequest struct {
	ID         int64
	Method     string
	Route      string
	StatusCode int
	DurationMs float64
	CreatedAt  time.Time
}
