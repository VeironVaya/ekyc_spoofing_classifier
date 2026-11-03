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

type KtpForgeryService struct {
	URL    string
	Client *http.Client
}

func NewKtpForgeryService(url string) *KtpForgeryService {
	return &KtpForgeryService{
		URL:    url,
		Client: &http.Client{Timeout: 15 * time.Second},
	}
}

func (s *KtpForgeryService) CallKtpForgery(imageBytes []byte, filename string, mockClass string) (*dtos.KtpForgeryResponse, error) {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	part, err := writer.CreateFormFile("file", filename)
	if err != nil {
		return nil, err
	}
	if _, err := part.Write(imageBytes); err != nil {
		return nil, err
	}
	if mockClass != "" {
		if err := writer.WriteField("mock_class", mockClass); err != nil {
			return nil, err
		}
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
		return nil, fmt.Errorf("ktp-forgery request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("ktp-forgery returned %d: %s", resp.StatusCode, string(body))
	}

	var result dtos.KtpForgeryResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

