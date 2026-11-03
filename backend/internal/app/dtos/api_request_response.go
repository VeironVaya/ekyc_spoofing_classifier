package dtos

import "time"

type APIRequestResponse struct {
	ID         int64     `json:"id"`
	Method     string    `json:"method"`
	Route      string    `json:"route"`
	StatusCode int       `json:"status_code"`
	DurationMs float64   `json:"duration_ms"`
	CreatedAt  time.Time `json:"created_at"`
}
