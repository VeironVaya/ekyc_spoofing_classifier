package controllers

import (
	"bytes"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/dtos"
	"ekyc-backend/internal/app/middleware"
	"ekyc-backend/internal/app/models"
	"ekyc-backend/internal/app/repositories"
	"ekyc-backend/internal/app/services"
	"ekyc-backend/internal/app/utils"
)

type LivenessController struct {
	Repo           *repositories.SpoofAttemptRepository
	InferenceSvc   *services.InferenceService
	DecisionSvc    *services.DecisionService
	UploadDir      string
	ApiRequestRepo *repositories.APIRequestRepository
}

func NewLivenessController(
	repo *repositories.SpoofAttemptRepository,
	inferenceSvc *services.InferenceService,
	decisionSvc *services.DecisionService,
	uploadDir string,
	apiRequestRepo *repositories.APIRequestRepository,
) *LivenessController {
	return &LivenessController{
		Repo:           repo,
		InferenceSvc:   inferenceSvc,
		DecisionSvc:    decisionSvc,
		UploadDir:      uploadDir,
		ApiRequestRepo: apiRequestRepo,
	}
}

func (lc *LivenessController) Verify(c *gin.Context) {
	var req dtos.VerifyRequest
	if err := c.ShouldBind(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	file, err := req.Selfie.Open()
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read selfie"})
		return
	}
	defer file.Close()

	imageBytes, err := io.ReadAll(file)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not read selfie"})
		return
	}

	idHash := utils.HashIDNumber(req.IDNumber)

	// History strictly before this attempt - the decision is based on what
	// came before, and this attempt joins the history only after logging.
	priorAttempts, err := lc.Repo.GetPriorAttempts(idHash)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not look up attempt history"})
		return
	}

	inferenceStart := time.Now()
	result, err := lc.InferenceSvc.CallInferenceService(imageBytes, req.Selfie.Filename)
	if err != nil {
		middleware.LogInternalCall(lc.ApiRequestRepo, "inference:/infer", inferenceStart, http.StatusBadGateway)
		c.JSON(http.StatusBadGateway, gin.H{"error": "inference service unavailable"})
		return
	}
	middleware.LogInternalCall(lc.ApiRequestRepo, "inference:/infer", inferenceStart, http.StatusOK)

	blurScore := result.BlurScore
	brightnessScore := result.BrightnessScore

	// A poor-quality capture is rejected before the spoof-decision logic ever
	// sees it - it isn't evidence of spoofing, so it must not go through
	// DecisionSvc.Decide or count toward the block-threshold history
	// (GetPriorAttempts already excludes rejected_poor_quality rows).
	if !result.QualityPassed {
		attempt := &models.SpoofAttempt{
			IDNumberHash:    idHash,
			PredictedClass:  "quality_rejected",
			Confidence:      0,
			Decision:        string(services.DecisionRejectedPoorQuality),
			BlurScore:       &blurScore,
			BrightnessScore: &brightnessScore,
		}
		if _, err := lc.Repo.LogAttempt(attempt); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "could not log attempt"})
			return
		}

		c.JSON(http.StatusOK, dtos.VerifyResponse{
			PredictedClass:      "quality_rejected",
			Decision:            string(services.DecisionRejectedPoorQuality),
			QualityPassed:       false,
			QualityRejectReason: result.QualityRejectReason,
		})
		return
	}

	decision := lc.DecisionSvc.Decide(result.PredictedClass, priorAttempts)

	var imagePath *string
	if !result.IsLive {
		ext := filepath.Ext(req.Selfie.Filename)
		if ext == "" {
			ext = ".jpg"
		}
		savedPath, err := utils.SaveEvidenceImage(lc.UploadDir, bytes.NewReader(imageBytes), ext)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "could not save evidence image"})
			return
		}
		imagePath = &savedPath
	}

	attempt := &models.SpoofAttempt{
		IDNumberHash:    idHash,
		PredictedClass:  result.PredictedClass,
		Confidence:      result.Confidence,
		ImagePath:       imagePath,
		Decision:        string(decision),
		BlurScore:       &blurScore,
		BrightnessScore: &brightnessScore,
	}
	if _, err := lc.Repo.LogAttempt(attempt); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not log attempt"})
		return
	}

	c.JSON(http.StatusOK, dtos.VerifyResponse{
		PredictedClass: result.PredictedClass,
		Confidence:     result.Confidence,
		IsLive:         result.IsLive,
		AllScores:      result.AllScores,
		Decision:       string(decision),
		QualityPassed:  true,
	})
}

func (lc *LivenessController) GetAttemptImage(c *gin.Context) {
	idParam := c.Param("id")
	id, err := strconv.ParseInt(idParam, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid attempt id"})
		return
	}

	attempt, err := lc.Repo.GetByID(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "attempt not found"})
		return
	}

	if attempt.ImagePath == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "no evidence image for this attempt"})
		return
	}

	if _, err := os.Stat(*attempt.ImagePath); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "evidence image missing on disk"})
		return
	}

	c.File(*attempt.ImagePath)
}

func (lc *LivenessController) ListAttempts(c *gin.Context) {
	limit := 100
	if v, err := strconv.Atoi(c.Query("limit")); err == nil && v > 0 && v <= 500 {
		limit = v
	}
	offset := 0
	if v, err := strconv.Atoi(c.Query("offset")); err == nil && v >= 0 {
		offset = v
	}

	attempts, err := lc.Repo.GetAllAttempts(limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not list attempts"})
		return
	}

	response := make([]dtos.AttemptResponse, 0, len(attempts))
	for _, a := range attempts {
		response = append(response, dtos.AttemptResponse{
			ID:              a.ID,
			IDNumberHash:    a.IDNumberHash,
			PredictedClass:  a.PredictedClass,
			Confidence:      a.Confidence,
			IsLive:          a.PredictedClass == "realperson",
			Decision:        a.Decision,
			HasImage:        a.ImagePath != nil,
			BlurScore:       a.BlurScore,
			BrightnessScore: a.BrightnessScore,
			CreatedAt:       a.CreatedAt,
		})
	}

	c.JSON(http.StatusOK, response)
}
