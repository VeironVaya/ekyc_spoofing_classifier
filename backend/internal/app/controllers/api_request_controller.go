package controllers

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/dtos"
	"ekyc-backend/internal/app/repositories"
)

type APIRequestController struct {
	Repo *repositories.APIRequestRepository
}

func NewAPIRequestController(repo *repositories.APIRequestRepository) *APIRequestController {
	return &APIRequestController{Repo: repo}
}

// ListAPIRequests serves a bounded recent window of raw rows for the admin
// dashboard to aggregate client-side (success/error rate, latency) - there's
// no server-side aggregation endpoint, matching how StatsOverview.jsx already
// aggregates attempts/registrations.
func (rc *APIRequestController) ListAPIRequests(c *gin.Context) {
	hours := 24
	if v, err := strconv.Atoi(c.Query("hours")); err == nil && v > 0 && v <= 168 {
		hours = v
	}
	limit := 2000
	if v, err := strconv.Atoi(c.Query("limit")); err == nil && v > 0 && v <= 5000 {
		limit = v
	}

	requests, err := rc.Repo.GetRecent(hours, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not list api requests"})
		return
	}

	response := make([]dtos.APIRequestResponse, 0, len(requests))
	for _, r := range requests {
		response = append(response, dtos.APIRequestResponse{
			ID:         r.ID,
			Method:     r.Method,
			Route:      r.Route,
			StatusCode: r.StatusCode,
			DurationMs: r.DurationMs,
			CreatedAt:  r.CreatedAt,
		})
	}

	c.JSON(http.StatusOK, response)
}
