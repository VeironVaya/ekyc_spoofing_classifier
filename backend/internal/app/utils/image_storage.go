package utils

import (
	"crypto/rand"
	"encoding/hex"
	"io"
	"os"
	"path/filepath"
	"time"
)

// SaveEvidenceImage writes image data under uploadDir/YYYY-MM-DD/<random>.ext
// and returns the path it was written to. Only called for flagged/spoofed
// attempts - genuine attempts never get an image saved.
func SaveEvidenceImage(uploadDir string, data io.Reader, ext string) (string, error) {
	dateFolder := time.Now().Format("2006-01-02")
	dir := filepath.Join(uploadDir, dateFolder)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}

	name, err := randomHex(16)
	if err != nil {
		return "", err
	}

	fullPath := filepath.Join(dir, name+ext)

	out, err := os.Create(fullPath)
	if err != nil {
		return "", err
	}
	defer out.Close()

	if _, err := io.Copy(out, data); err != nil {
		return "", err
	}

	return fullPath, nil
}

func randomHex(n int) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}
