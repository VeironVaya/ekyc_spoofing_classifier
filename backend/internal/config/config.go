package config

import (
	"log"
	"os"

	"github.com/joho/godotenv"
)

type Config struct {
	Port          string
	DBHost        string
	DBPort        string
	DBUser        string
	DBPassword    string
	DBName        string
	InferenceURL     string
	EkycCheckURL     string
	KtpForgeryURL    string
	PipelineCheckURL string
	AdminAPIKey      string
	UploadDir        string
	EkycUploadDir    string
}

func Load() *Config {
	if err := godotenv.Load(); err != nil {
		log.Println("no .env file found, reading from OS environment")
	}

	return &Config{
		Port:             getEnv("PORT", "8080"),
		DBHost:           getEnv("DB_HOST", "localhost"),
		DBPort:           getEnv("DB_PORT", "3306"),
		DBUser:           getEnv("DB_USER", "root"),
		DBPassword:       getEnv("DB_PASSWORD", ""),
		DBName:           getEnv("DB_NAME", "ekyc_liveness"),
		InferenceURL:     getEnv("INFERENCE_URL", "http://localhost:8000/infer"),
		EkycCheckURL:     getEnv("EKYC_CHECK_URL", "http://localhost:8000/ekyc-check"),
		KtpForgeryURL:    getEnv("KTP_FORGERY_URL", "http://localhost:8000/ktp-forgery"),
		PipelineCheckURL: getEnv("PIPELINE_CHECK_URL", "http://localhost:8000/pipeline-check"),
		AdminAPIKey:      getEnv("ADMIN_API_KEY", ""),
		UploadDir:        getEnv("UPLOAD_DIR", "data/uploads"),
		EkycUploadDir:    getEnv("EKYC_UPLOAD_DIR", "data/registrations"),
	}
}

func getEnv(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return fallback
}
