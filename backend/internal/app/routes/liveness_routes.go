package routes

import (
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/controllers"
)

func RegisterRoutes(r *gin.Engine, lc *controllers.LivenessController, adminAPIKey string) {
	r.POST("/verify", lc.Verify)

	admin := r.Group("/admin")
	admin.Use(adminAuthMiddleware(adminAPIKey))
	{
		admin.GET("/attempts", lc.ListAttempts)
		admin.GET("/attempts/:id/image", lc.GetAttemptImage)
	}
}

func adminAuthMiddleware(apiKey string) gin.HandlerFunc {
	return func(c *gin.Context) {
		token := strings.TrimPrefix(c.GetHeader("Authorization"), "Bearer ")
		if apiKey == "" || token != apiKey {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
			return
		}
		c.Next()
	}
}
