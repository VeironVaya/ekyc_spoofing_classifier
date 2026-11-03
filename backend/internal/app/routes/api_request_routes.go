package routes

import (
	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/controllers"
)

func RegisterAPIRequestRoutes(r *gin.Engine, rc *controllers.APIRequestController, adminAPIKey string) {
	admin := r.Group("/admin")
	admin.Use(adminAuthMiddleware(adminAPIKey))
	{
		admin.GET("/api-requests", rc.ListAPIRequests)
	}
}
