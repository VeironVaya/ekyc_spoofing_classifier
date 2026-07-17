package utils

import (
	"crypto/sha256"
	"encoding/hex"
)

func HashIDNumber(idNumber string) string {
	sum := sha256.Sum256([]byte(idNumber))
	return hex.EncodeToString(sum[:])
}
