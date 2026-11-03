package services

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"time"

	"ekyc-backend/internal/app/dtos"
)

type OCRFields struct {
	NIK         *string `json:"nik"`
	Name        *string `json:"name"`
	DateOfBirth *string `json:"date_of_birth"`
	RawText     string  `json:"raw_text"`
}

type FaceMatchResult struct {
	Verified  bool     `json:"verified"`
	Distance  *float64 `json:"distance"`
	Threshold *float64 `json:"threshold"`
	Error     *string  `json:"error"`
}

type ImageQuality struct {
	BlurScore           float64 `json:"blur_score"`
	BrightnessScore     float64 `json:"brightness_score"`
	FaceAreaRatio       float64 `json:"face_area_ratio"`
	QualityPassed       bool    `json:"quality_passed"`
	QualityRejectReason *string `json:"quality_reject_reason"`
}

type EkycCheckResult struct {
	OCR           OCRFields       `json:"ocr"`
	FaceMatch     FaceMatchResult `json:"face_match"`
	IDCardQuality ImageQuality    `json:"id_card_quality"`
	SelfieQuality ImageQuality    `json:"selfie_quality"`
}

type CompletePipelineResult struct {
	KtpForgery     *dtos.KtpForgeryResponse `json:"ktp_forgery"`
	OCR            OCRFields                `json:"ocr"`
	FaceMatch      FaceMatchResult          `json:"face_match"`
	SelfieLiveness *InferenceResult         `json:"selfie_liveness"`
	IDCardQuality  ImageQuality             `json:"id_card_quality"`
	SelfieQuality  ImageQuality             `json:"selfie_quality"`
}

type EkycService struct {
	URL         string
	PipelineURL string
	Client      *http.Client
}

func NewEkycService(url string, pipelineURL string) *EkycService {
	return &EkycService{
		URL:         url,
		PipelineURL: pipelineURL,
		Client:      &http.Client{Timeout: 35 * time.Second},
	}
}

// CallEkycCheck sends the ID card and selfie to the Python inference
// microservice's combined OCR + face-match endpoint.
func (s *EkycService) CallEkycCheck(idCardBytes []byte, idCardFilename string, selfieBytes []byte, selfieFilename string) (*EkycCheckResult, error) {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	if err := writeFormFile(writer, "id_card", idCardFilename, idCardBytes); err != nil {
		return nil, err
	}
	if err := writeFormFile(writer, "selfie", selfieFilename, selfieBytes); err != nil {
		return nil, err
	}
	if err := writer.Close(); err != nil {
		return nil, err
	}

	req, err := http.NewRequest(http.MethodPost, s.URL, &buf)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := s.Client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ekyc-check request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("ekyc-check returned %d: %s", resp.StatusCode, string(body))
	}

	var result EkycCheckResult
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

// CallCompletePipelineCheck executes Mode 3: KTP Doc-PAD + OCR + Face Match + Selfie Liveness.
func (s *EkycService) CallCompletePipelineCheck(
	idCardBytes []byte,
	idCardFilename string,
	selfieBytes []byte,
	selfieFilename string,
	mockKtpClass string,
) (*CompletePipelineResult, error) {
	endpoint := s.PipelineURL
	if endpoint == "" {
		endpoint = "http://localhost:8000/pipeline-check"
	}

	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	if err := writeFormFile(writer, "id_card", idCardFilename, idCardBytes); err != nil {
		return nil, err
	}
	if err := writeFormFile(writer, "selfie", selfieFilename, selfieBytes); err != nil {
		return nil, err
	}
	if mockKtpClass != "" {
		if err := writer.WriteField("mock_ktp_class", mockKtpClass); err != nil {
			return nil, err
		}
	}
	if err := writer.Close(); err != nil {
		return nil, err
	}

	req, err := http.NewRequest(http.MethodPost, endpoint, &buf)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := s.Client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("pipeline-check request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("pipeline-check returned %d: %s", resp.StatusCode, string(body))
	}

	var result CompletePipelineResult
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

func writeFormFile(w *multipart.Writer, fieldname, filename string, data []byte) error {
	part, err := w.CreateFormFile(fieldname, filename)
	if err != nil {
		return err
	}
	_, err = part.Write(data)
	return err
}
