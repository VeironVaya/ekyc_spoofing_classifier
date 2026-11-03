package middleware

import (
	"log"
	"strings"
	"time"

	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/models"
	"ekyc-backend/internal/app/repositories"
)

// APM records method/route/status/duration for every public request into
// api_requests. Routes under /admin are skipped, including the dashboard's
// own polling of this data, so the panel doesn't pollute the stats it shows.
// An insert failure is logged and never aborts the real response.
func APM(repo *repositories.APIRequestRepository) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()

		route := c.FullPath()
		if route == "" || strings.HasPrefix(route, "/admin") {
			return
		}

		logRequest(repo, c.Request.Method, route, c.Writer.Status(), start)
	}
}

// LogInternalCall records a Go->Python call's timing into the same
// api_requests table the HTTP middleware writes to, under a synthetic route
// (e.g. "inference:/infer") so it shows up as its own row in the per-route
// breakdown - these calls never pass through Gin's own request cycle.
func LogInternalCall(repo *repositories.APIRequestRepository, route string, start time.Time, statusCode int) {
	logRequest(repo, "POST", route, statusCode, start)
}

func logRequest(repo *repositories.APIRequestRepository, method, route string, statusCode int, start time.Time) {
	req := &models.APIRequest{
		Method:     method,
		Route:      route,
		StatusCode: statusCode,
		DurationMs: float64(time.Since(start).Microseconds()) / 1000.0,
	}
	if err := repo.LogRequest(req); err != nil {
		log.Printf("apm: could not log request for %s %s: %v", method, route, err)
	}
}
