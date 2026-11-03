package controllers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/dtos"
	"ekyc-backend/internal/app/middleware"
	"ekyc-backend/internal/app/repositories"
	"ekyc-backend/internal/app/services"
)

type KtpForgeryController struct {
	ForgerySvc     *services.KtpForgeryService
	ApiRequestRepo *repositories.APIRequestRepository
}

func NewKtpForgeryController(forgerySvc *services.KtpForgeryService, apiRequestRepo *repositories.APIRequestRepository) *KtpForgeryController {
	return &KtpForgeryController{
		ForgerySvc:     forgerySvc,
		ApiRequestRepo: apiRequestRepo,
	}
}

func (kc *KtpForgeryController) CheckKtp(c *gin.Context) {
	var req dtos.KtpForgeryRequest
	if err := c.ShouldBind(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	imageBytes, err := readMultipartFile(req.File)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read image file"})
		return
	}

	start := time.Now()
	res, err := kc.ForgerySvc.CallKtpForgery(imageBytes, req.File.Filename, req.MockClass)
	if err != nil {
		middleware.LogInternalCall(kc.ApiRequestRepo, "inference:/ktp-forgery", start, http.StatusBadGateway)
		c.JSON(http.StatusBadGateway, gin.H{"error": "KTP forgery detection service unavailable"})
		return
	}
	middleware.LogInternalCall(kc.ApiRequestRepo, "inference:/ktp-forgery", start, http.StatusOK)

	c.JSON(http.StatusOK, res)
}

