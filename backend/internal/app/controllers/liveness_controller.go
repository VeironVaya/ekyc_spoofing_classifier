package controllers

import (
	"bytes"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"

	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/dtos"
	"ekyc-backend/internal/app/models"
	"ekyc-backend/internal/app/repositories"
	"ekyc-backend/internal/app/services"
	"ekyc-backend/internal/app/utils"
)

type LivenessController struct {
	Repo         *repositories.SpoofAttemptRepository
	InferenceSvc *services.InferenceService
	DecisionSvc  *services.DecisionService
	UploadDir    string
}

func NewLivenessController(
	repo *repositories.SpoofAttemptRepository,
	inferenceSvc *services.InferenceService,
	decisionSvc *services.DecisionService,
	uploadDir string,
) *LivenessController {
	return &LivenessController{
		Repo:         repo,
		InferenceSvc: inferenceSvc,
		DecisionSvc:  decisionSvc,
		UploadDir:    uploadDir,
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

	result, err := lc.InferenceSvc.CallInferenceService(imageBytes, req.Selfie.Filename)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "inference service unavailable"})
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
		IDNumberHash:   idHash,
		PredictedClass: result.PredictedClass,
		Confidence:     result.Confidence,
		ImagePath:      imagePath,
		Decision:       string(decision),
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
			ID:             a.ID,
			IDNumberHash:   a.IDNumberHash,
			PredictedClass: a.PredictedClass,
			Confidence:     a.Confidence,
			IsLive:         a.PredictedClass == "realperson",
			Decision:       a.Decision,
			HasImage:       a.ImagePath != nil,
			CreatedAt:      a.CreatedAt,
		})
	}

	c.JSON(http.StatusOK, response)
}
