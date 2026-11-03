package controllers

import (
	"bytes"
	"database/sql"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"

	"ekyc-backend/internal/app/dtos"
	"ekyc-backend/internal/app/models"
	"ekyc-backend/internal/app/repositories"
	"ekyc-backend/internal/app/services"
	"ekyc-backend/internal/app/utils"
)

var nikFormatPattern = regexp.MustCompile(`^\d{16}$`)

type EkycController struct {
	Repo           *repositories.RegistrationRepository
	InferenceSvc   *services.InferenceService
	EkycSvc        *services.EkycService
	UploadDir      string
	ApiRequestRepo *repositories.APIRequestRepository
}

func NewEkycController(
	repo *repositories.RegistrationRepository,
	inferenceSvc *services.InferenceService,
	ekycSvc *services.EkycService,
	uploadDir string,
	apiRequestRepo *repositories.APIRequestRepository,
) *EkycController {
	return &EkycController{
		Repo:           repo,
		InferenceSvc:   inferenceSvc,
		EkycSvc:        ekycSvc,
		UploadDir:      uploadDir,
		ApiRequestRepo: apiRequestRepo,
	}
}

// Preview runs the same checks as Register (liveness + OCR + face-match) but
// never persists anything - it lets the frontend show the user an editable
// form pre-filled with the extracted fields before they confirm registration.
func (ec *EkycController) Preview(c *gin.Context) {
	var req dtos.PreviewRequest
	if err := c.ShouldBind(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	idCardBytes, err := readMultipartFile(req.IDCard)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read ID card image"})
		return
	}
	selfieBytes, err := readMultipartFile(req.Selfie)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read selfie"})
		return
	}

	livenessResult, err := ec.InferenceSvc.CallInferenceService(selfieBytes, req.Selfie.Filename)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "liveness check unavailable"})
		return
	}

	ekycResult, err := ec.EkycSvc.CallEkycCheck(idCardBytes, req.IDCard.Filename, selfieBytes, req.Selfie.Filename)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "eKYC check unavailable"})
		return
	}

	response := dtos.RegisterPreviewResponse{
		RawOCRText:             ekycResult.OCR.RawText,
		LivenessPredictedClass: livenessResult.PredictedClass,
		LivenessConfidence:     livenessResult.Confidence,
		IsLive:                 livenessResult.IsLive,
		FaceMatchVerified:      ekycResult.FaceMatch.Verified,
		FaceMatchDistance:      ekycResult.FaceMatch.Distance,
	}
	if ekycResult.OCR.NIK != nil {
		response.ExtractedNIK = *ekycResult.OCR.NIK
	}
	if ekycResult.OCR.Name != nil {
		response.ExtractedName = *ekycResult.OCR.Name
	}
	if ekycResult.OCR.DateOfBirth != nil {
		response.ExtractedDOB = *ekycResult.OCR.DateOfBirth
	}
	if ekycResult.FaceMatch.Error != nil {
		response.FaceMatchError = *ekycResult.FaceMatch.Error
	}

	c.JSON(http.StatusOK, response)
}

func (ec *EkycController) Register(c *gin.Context) {
	var req dtos.RegisterRequest
	if err := c.ShouldBind(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	idCardBytes, err := readMultipartFile(req.IDCard)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read ID card image"})
		return
	}
	selfieBytes, err := readMultipartFile(req.Selfie)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read selfie"})
		return
	}

	livenessResult, err := ec.InferenceSvc.CallInferenceService(selfieBytes, req.Selfie.Filename)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "liveness check unavailable"})
		return
	}

	ekycResult, err := ec.EkycSvc.CallEkycCheck(idCardBytes, req.IDCard.Filename, selfieBytes, req.Selfie.Filename)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "eKYC check unavailable"})
		return
	}

	finalNIK := strings.TrimSpace(req.NIK)
	if finalNIK == "" && ekycResult.OCR.NIK != nil {
		finalNIK = *ekycResult.OCR.NIK
	}
	finalName := strings.TrimSpace(req.Name)
	if finalName == "" && ekycResult.OCR.Name != nil {
		finalName = *ekycResult.OCR.Name
	}
	finalDOB := strings.TrimSpace(req.DOB)
	if finalDOB == "" && ekycResult.OCR.DateOfBirth != nil {
		finalDOB = *ekycResult.OCR.DateOfBirth
	}

	decision := decideRegistration(livenessResult.IsLive, ekycResult.FaceMatch.Verified, finalNIK)

	idCardPath, err := utils.SaveEvidenceImage(ec.UploadDir, bytes.NewReader(idCardBytes), extOf(req.IDCard.Filename))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not save id card image"})
		return
	}
	selfiePath, err := utils.SaveEvidenceImage(ec.UploadDir, bytes.NewReader(selfieBytes), extOf(req.Selfie.Filename))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not save selfie image"})
		return
	}

	var nikHash *string
	if finalNIK != "" {
		h := utils.HashIDNumber(finalNIK)
		nikHash = &h
	}
	var namePtr, dobPtr *string
	if finalName != "" {
		namePtr = &finalName
	}
	if finalDOB != "" {
		dobPtr = &finalDOB
	}

	reg := &models.Registration{
		NIKHash:                nikHash,
		ExtractedName:          namePtr,
		ExtractedDOB:           dobPtr,
		LivenessPredictedClass: livenessResult.PredictedClass,
		LivenessConfidence:     livenessResult.Confidence,
		FaceMatchVerified:      ekycResult.FaceMatch.Verified,
		FaceMatchDistance:      ekycResult.FaceMatch.Distance,
		IDCardImagePath:        &idCardPath,
		SelfieImagePath:        &selfiePath,
		Decision:               decision,
		AutomatedDecision:      &decision,
		IDCardBlurScore:        &ekycResult.IDCardQuality.BlurScore,
		IDCardBrightnessScore:  &ekycResult.IDCardQuality.BrightnessScore,
		SelfieBlurScore:        &ekycResult.SelfieQuality.BlurScore,
		SelfieBrightnessScore:  &ekycResult.SelfieQuality.BrightnessScore,
	}

	if _, err := ec.Repo.LogRegistration(reg); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not log registration"})
		return
	}

	response := dtos.RegisterResponse{
		RawOCRText:             ekycResult.OCR.RawText,
		LivenessPredictedClass: livenessResult.PredictedClass,
		LivenessConfidence:     livenessResult.Confidence,
		IsLive:                 livenessResult.IsLive,
		FaceMatchVerified:      ekycResult.FaceMatch.Verified,
		FaceMatchDistance:      ekycResult.FaceMatch.Distance,
		ExtractedNIK:           finalNIK,
		ExtractedName:          finalName,
		ExtractedDOB:           finalDOB,
		Decision:               decision,
	}
	if ekycResult.FaceMatch.Error != nil {
		response.FaceMatchError = *ekycResult.FaceMatch.Error
	}

	c.JSON(http.StatusOK, response)
}

// PipelinePreview executes Mode 3 preview (KTP Doc-PAD + OCR + Selfie Liveness + Face Match).
func (ec *EkycController) PipelinePreview(c *gin.Context) {
	var req dtos.PipelinePreviewRequest
	if err := c.ShouldBind(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	idCardBytes, err := readMultipartFile(req.IDCard)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read ID card image"})
		return
	}
	selfieBytes, err := readMultipartFile(req.Selfie)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read selfie"})
		return
	}

	res, err := ec.EkycSvc.CallCompletePipelineCheck(idCardBytes, req.IDCard.Filename, selfieBytes, req.Selfie.Filename, req.MockKtpClass)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "complete pipeline service unavailable"})
		return
	}

	if !res.IDCardQuality.QualityPassed || !res.SelfieQuality.QualityPassed {
		reason := res.IDCardQuality.QualityRejectReason
		if reason == nil {
			reason = res.SelfieQuality.QualityRejectReason
		}
		c.JSON(http.StatusOK, dtos.PipelinePreviewResponse{
			LivenessPredictedClass: "quality_rejected",
			QualityPassed:          false,
			QualityRejectReason:    reason,
		})
		return
	}

	response := dtos.PipelinePreviewResponse{
		RawOCRText:        res.OCR.RawText,
		FaceMatchVerified: res.FaceMatch.Verified,
		FaceMatchDistance: res.FaceMatch.Distance,
		KtpForgery:        res.KtpForgery,
		QualityPassed:     true,
	}

	if res.SelfieLiveness != nil {
		response.LivenessPredictedClass = res.SelfieLiveness.PredictedClass
		response.LivenessConfidence = res.SelfieLiveness.Confidence
		response.IsLive = res.SelfieLiveness.IsLive
	}
	if res.OCR.NIK != nil {
		response.ExtractedNIK = *res.OCR.NIK
	}
	if res.OCR.Name != nil {
		response.ExtractedName = *res.OCR.Name
	}
	if res.OCR.DateOfBirth != nil {
		response.ExtractedDOB = *res.OCR.DateOfBirth
	}
	if res.FaceMatch.Error != nil {
		response.FaceMatchError = *res.FaceMatch.Error
	}

	c.JSON(http.StatusOK, response)
}

// PipelineRegister handles Mode 3 complete pipeline confirmation. It re-verifies KTP
// Doc-PAD authenticity, selfie face liveness, and 1:1 ArcFace matching on raw bytes server-side.
func (ec *EkycController) PipelineRegister(c *gin.Context) {
	var req dtos.RegisterRequest
	if err := c.ShouldBind(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	idCardBytes, err := readMultipartFile(req.IDCard)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read ID card image"})
		return
	}
	selfieBytes, err := readMultipartFile(req.Selfie)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "could not read selfie"})
		return
	}

	res, err := ec.EkycSvc.CallCompletePipelineCheck(idCardBytes, req.IDCard.Filename, selfieBytes, req.Selfie.Filename, "")
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "complete pipeline service unavailable"})
		return
	}

	if !res.IDCardQuality.QualityPassed || !res.SelfieQuality.QualityPassed {
		c.JSON(http.StatusOK, dtos.RegisterResponse{
			LivenessPredictedClass: "quality_rejected",
			Decision:               "rejected_poor_quality",
		})
		return
	}

	finalNIK := strings.TrimSpace(req.NIK)
	if finalNIK == "" && res.OCR.NIK != nil {
		finalNIK = *res.OCR.NIK
	}
	finalName := strings.TrimSpace(req.Name)
	if finalName == "" && res.OCR.Name != nil {
		finalName = *res.OCR.Name
	}
	finalDOB := strings.TrimSpace(req.DOB)
	if finalDOB == "" && res.OCR.DateOfBirth != nil {
		finalDOB = *res.OCR.DateOfBirth
	}

	isLive := false
	predictedClass := "unknown"
	confidence := 0.0
	if res.SelfieLiveness != nil {
		isLive = res.SelfieLiveness.IsLive
		predictedClass = res.SelfieLiveness.PredictedClass
		confidence = res.SelfieLiveness.Confidence
	}

	ktpAuthentic := false
	if res.KtpForgery != nil {
		ktpAuthentic = res.KtpForgery.IsAuthentic
	}

	decision := decidePipelineRegistration(isLive, ktpAuthentic, res.FaceMatch.Verified, finalNIK)

	idCardPath, err := utils.SaveEvidenceImage(ec.UploadDir, bytes.NewReader(idCardBytes), extOf(req.IDCard.Filename))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not save id card image"})
		return
	}
	selfiePath, err := utils.SaveEvidenceImage(ec.UploadDir, bytes.NewReader(selfieBytes), extOf(req.Selfie.Filename))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not save selfie image"})
		return
	}

	var nikHash *string
	if finalNIK != "" {
		h := utils.HashIDNumber(finalNIK)
		nikHash = &h
	}
	var namePtr, dobPtr *string
	if finalName != "" {
		namePtr = &finalName
	}
	if finalDOB != "" {
		dobPtr = &finalDOB
	}

	reg := &models.Registration{
		NIKHash:                nikHash,
		ExtractedName:          namePtr,
		ExtractedDOB:           dobPtr,
		LivenessPredictedClass: predictedClass,
		LivenessConfidence:     confidence,
		FaceMatchVerified:      res.FaceMatch.Verified,
		FaceMatchDistance:      res.FaceMatch.Distance,
		IDCardImagePath:        &idCardPath,
		SelfieImagePath:        &selfiePath,
		Decision:               decision,
		AutomatedDecision:      &decision,
		IDCardBlurScore:        &res.IDCardQuality.BlurScore,
		IDCardBrightnessScore:  &res.IDCardQuality.BrightnessScore,
		SelfieBlurScore:        &res.SelfieQuality.BlurScore,
		SelfieBrightnessScore:  &res.SelfieQuality.BrightnessScore,
	}

	if _, err := ec.Repo.LogRegistration(reg); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not log registration"})
		return
	}

	response := dtos.RegisterResponse{
		RawOCRText:             res.OCR.RawText,
		LivenessPredictedClass: predictedClass,
		LivenessConfidence:     confidence,
		IsLive:                 isLive,
		FaceMatchVerified:      res.FaceMatch.Verified,
		FaceMatchDistance:      res.FaceMatch.Distance,
		ExtractedNIK:           finalNIK,
		ExtractedName:          finalName,
		ExtractedDOB:           finalDOB,
		Decision:               decision,
	}
	if res.FaceMatch.Error != nil {
		response.FaceMatchError = *res.FaceMatch.Error
	}

	c.JSON(http.StatusOK, response)
}

func (ec *EkycController) ListRegistrations(c *gin.Context) {
	limit := 100
	if v, err := strconv.Atoi(c.Query("limit")); err == nil && v > 0 && v <= 500 {
		limit = v
	}
	offset := 0
	if v, err := strconv.Atoi(c.Query("offset")); err == nil && v >= 0 {
		offset = v
	}

	regs, err := ec.Repo.GetAllRegistrations(limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not list registrations"})
		return
	}

	response := make([]dtos.RegistrationResponse, 0, len(regs))
	for _, r := range regs {
		item := dtos.RegistrationResponse{
			ID:                     r.ID,
			LivenessPredictedClass: r.LivenessPredictedClass,
			LivenessConfidence:     r.LivenessConfidence,
			FaceMatchVerified:      r.FaceMatchVerified,
			FaceMatchDistance:      r.FaceMatchDistance,
			Decision:               r.Decision,
			IDCardBlurScore:        r.IDCardBlurScore,
			IDCardBrightnessScore:  r.IDCardBrightnessScore,
			SelfieBlurScore:        r.SelfieBlurScore,
			SelfieBrightnessScore:  r.SelfieBrightnessScore,
			HasIDCardImage:         r.IDCardImagePath != nil,
			HasSelfieImage:         r.SelfieImagePath != nil,
			CreatedAt:              r.CreatedAt,
		}
		if r.AutomatedDecision != nil {
			item.AutomatedDecision = *r.AutomatedDecision
		}
		if r.NIKHash != nil {
			item.NIKHash = *r.NIKHash
		}
		if r.ExtractedName != nil {
			item.ExtractedName = *r.ExtractedName
		}
		if r.ExtractedDOB != nil {
			item.ExtractedDOB = *r.ExtractedDOB
		}
		response = append(response, item)
	}

	c.JSON(http.StatusOK, response)
}

func (ec *EkycController) GetRegistrationImage(c *gin.Context) {
	idParam := c.Param("id")
	id, err := strconv.ParseInt(idParam, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid registration id"})
		return
	}

	imageType := c.DefaultQuery("type", "selfie")
	if imageType != "selfie" && imageType != "id_card" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "type must be selfie or id_card"})
		return
	}

	reg, err := ec.Repo.GetByID(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "registration not found"})
		return
	}

	path := reg.SelfieImagePath
	if imageType == "id_card" {
		path = reg.IDCardImagePath
	}

	if path == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "no image for this registration"})
		return
	}

	if _, err := os.Stat(*path); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "image missing on disk"})
		return
	}

	c.File(*path)
}

var allowedManualDecisions = map[string]bool{
	"approved":        true,
	"rejected_manual": true,
}

// ReviewRegistration lets an admin manually set a registration's outcome
// after inspecting the ID card/selfie evidence - mainly for clearing the
// manual_review backlog, but not restricted to it. "rejected_manual" is kept
// distinct from the automated rejected_spoof/rejected_face_mismatch reasons
// so the log still shows whether a rejection was a human call or automatic.
func (ec *EkycController) ReviewRegistration(c *gin.Context) {
	idParam := c.Param("id")
	id, err := strconv.ParseInt(idParam, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid registration id"})
		return
	}

	var body struct {
		Decision string `json:"decision"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if !allowedManualDecisions[body.Decision] {
		c.JSON(http.StatusBadRequest, gin.H{"error": "decision must be 'approved' or 'rejected_manual'"})
		return
	}

	if err := ec.Repo.UpdateDecision(id, body.Decision); err != nil {
		if err == sql.ErrNoRows {
			c.JSON(http.StatusNotFound, gin.H{"error": "registration not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not update decision"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"id": id, "decision": body.Decision})
}

func decidePipelineRegistration(isLive bool, ktpAuthentic bool, faceVerified bool, nik string) string {
	if !isLive {
		return "rejected_spoof"
	}
	if !ktpAuthentic {
		return "rejected_ktp_forgery"
	}
	if !faceVerified {
		return "rejected_face_mismatch"
	}
	if !nikFormatPattern.MatchString(nik) {
		return "manual_review"
	}
	return "approved"
}

func decideRegistration(isLive bool, faceVerified bool, nik string) string {
	if !isLive {
		return "rejected_spoof"
	}
	if !faceVerified {
		return "rejected_face_mismatch"
	}
	if !nikFormatPattern.MatchString(nik) {
		return "manual_review"
	}
	return "approved"
}

func readMultipartFile(fh *multipart.FileHeader) ([]byte, error) {
	file, err := fh.Open()
	if err != nil {
		return nil, err
	}
	defer file.Close()
	return io.ReadAll(file)
}

func extOf(filename string) string {
	ext := filepath.Ext(filename)
	if ext == "" {
		return ".jpg"
	}
	return ext
}
