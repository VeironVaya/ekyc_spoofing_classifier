package routes

import (
	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/controllers"
)

func RegisterEkycRoutes(r *gin.Engine, ec *controllers.EkycController, adminAPIKey string) {
	r.POST("/register/preview", ec.Preview)
	r.POST("/register", ec.Register)

	admin := r.Group("/admin")
	admin.Use(adminAuthMiddleware(adminAPIKey))
	{
		admin.GET("/registrations", ec.ListRegistrations)
		admin.GET("/registrations/:id/image", ec.GetRegistrationImage)
		admin.PATCH("/registrations/:id/decision", ec.ReviewRegistration)
	}
}
