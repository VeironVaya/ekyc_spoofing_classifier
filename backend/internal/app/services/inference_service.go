package services

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"time"
)

type InferenceResult struct {
	PredictedClass string             `json:"predicted_class"`
	Confidence     float64            `json:"confidence"`
	IsLive         bool               `json:"is_live"`
	AllScores      map[string]float64 `json:"all_scores"`
}

type InferenceService struct {
	URL    string
	Client *http.Client
}

func NewInferenceService(url string) *InferenceService {
	return &InferenceService{
		URL:    url,
		Client: &http.Client{Timeout: 15 * time.Second},
	}
}

// CallInferenceService sends the selfie to the Python inference microservice
// and returns its classification result.
func (s *InferenceService) CallInferenceService(imageBytes []byte, filename string) (*InferenceResult, error) {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	part, err := writer.CreateFormFile("file", filename)
	if err != nil {
		return nil, err
	}
	if _, err := part.Write(imageBytes); err != nil {
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
		return nil, fmt.Errorf("inference service request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("inference service returned %d: %s", resp.StatusCode, string(body))
	}

	var result InferenceResult
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}

	return &result, nil
}
