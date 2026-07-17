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

type EkycCheckResult struct {
	OCR       OCRFields       `json:"ocr"`
	FaceMatch FaceMatchResult `json:"face_match"`
}

type EkycService struct {
	URL    string
	Client *http.Client
}

func NewEkycService(url string) *EkycService {
	return &EkycService{
		URL: url,
		// ArcFace weights are baked into the inference image at build time, so
		// there's no cold-start download in the request path anymore - OCR and
		// face-match now also run concurrently, so 30s is a generous ceiling.
		Client: &http.Client{Timeout: 30 * time.Second},
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

func writeFormFile(writer *multipart.Writer, field, filename string, data []byte) error {
	part, err := writer.CreateFormFile(field, filename)
	if err != nil {
		return err
	}
	_, err = part.Write(data)
	return err
}
