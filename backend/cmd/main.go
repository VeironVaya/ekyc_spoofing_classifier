package main

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/controllers"
	"ekyc-backend/internal/app/middleware"
	"ekyc-backend/internal/app/repositories"
	"ekyc-backend/internal/app/routes"
	"ekyc-backend/internal/app/services"
	"ekyc-backend/internal/config"
)

func main() {
	cfg := config.Load()

	db, err := config.ConnectDB(cfg)
	if err != nil {
		log.Fatalf("failed to connect to database: %v", err)
	}
	defer db.Close()

	apiRequestRepo := repositories.NewAPIRequestRepository(db)

	repo := repositories.NewSpoofAttemptRepository(db)
	inferenceSvc := services.NewInferenceService(cfg.InferenceURL)
	decisionSvc := services.NewDecisionService()
	lc := controllers.NewLivenessController(repo, inferenceSvc, decisionSvc, cfg.UploadDir, apiRequestRepo)

	registrationRepo := repositories.NewRegistrationRepository(db)
	ekycSvc := services.NewEkycService(cfg.EkycCheckURL, cfg.PipelineCheckURL)
	ec := controllers.NewEkycController(registrationRepo, inferenceSvc, ekycSvc, cfg.EkycUploadDir, apiRequestRepo)

	forgerySvc := services.NewKtpForgeryService(cfg.KtpForgeryURL)
	kc := controllers.NewKtpForgeryController(forgerySvc, apiRequestRepo)

	rc := controllers.NewAPIRequestController(apiRequestRepo)

	r := gin.Default()
	r.Use(corsMiddleware())
	r.Use(middleware.APM(apiRequestRepo))
	routes.RegisterRoutes(r, lc, cfg.AdminAPIKey)
	routes.RegisterEkycRoutes(r, ec, kc, cfg.AdminAPIKey)
	routes.RegisterAPIRequestRoutes(r, rc, cfg.AdminAPIKey)

	log.Printf("listening on :%s", cfg.Port)
	if err := r.Run(":" + cfg.Port); err != nil {
		log.Fatalf("server failed: %v", err)
	}
}

// corsMiddleware allows the React dev server (a different origin locally)
// to call this API. In production Nginx fronts both, so this is mainly a
// local-dev convenience.
func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if c.Request.Method == http.MethodOptions {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}
