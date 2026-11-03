package routes

import (
	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/controllers"
)

func RegisterEkycRoutes(r *gin.Engine, ec *controllers.EkycController, kc *controllers.KtpForgeryController, adminAPIKey string) {
	r.POST("/register/preview", ec.Preview)
	r.POST("/register", ec.Register)

	// Mode 3: Complete Pipeline
	r.POST("/pipeline/preview", ec.PipelinePreview)
	r.POST("/pipeline/register", ec.PipelineRegister)

	// Mode 4: Standalone KTP Forgery Test
	if kc != nil {
		r.POST("/ktp-forgery", kc.CheckKtp)
	}

	admin := r.Group("/admin")
	admin.Use(adminAuthMiddleware(adminAPIKey))
	{
		admin.GET("/registrations", ec.ListRegistrations)
		admin.GET("/registrations/:id/image", ec.GetRegistrationImage)
		admin.PATCH("/registrations/:id/decision", ec.ReviewRegistration)
	}
}
