package repositories

import (
	"database/sql"

	"ekyc-backend/internal/app/models"
)

type APIRequestRepository struct {
	DB *sql.DB
}

func NewAPIRequestRepository(db *sql.DB) *APIRequestRepository {
	return &APIRequestRepository{DB: db}
}

func (r *APIRequestRepository) LogRequest(req *models.APIRequest) error {
	_, err := r.DB.Exec(
		`INSERT INTO api_requests (method, route, status_code, duration_ms) VALUES (?, ?, ?, ?)`,
		req.Method, req.Route, req.StatusCode, req.DurationMs,
	)
	return err
}

// GetRecent returns rows from the last windowHours, most recent first, capped
// at limit - the dashboard aggregates this bounded window client-side rather
// than via a server-side SQL aggregation endpoint.
func (r *APIRequestRepository) GetRecent(windowHours, limit int) ([]models.APIRequest, error) {
	rows, err := r.DB.Query(
		`SELECT id, method, route, status_code, duration_ms, created_at
		 FROM api_requests
		 WHERE created_at >= DATE_SUB(NOW(), INTERVAL ? HOUR)
		 ORDER BY created_at DESC LIMIT ?`,
		windowHours, limit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var requests []models.APIRequest
	for rows.Next() {
		var req models.APIRequest
		if err := rows.Scan(&req.ID, &req.Method, &req.Route, &req.StatusCode, &req.DurationMs, &req.CreatedAt); err != nil {
			return nil, err
		}
		requests = append(requests, req)
	}
	return requests, rows.Err()
}
