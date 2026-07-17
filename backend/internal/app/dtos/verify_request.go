package dtos

import "mime/multipart"

type VerifyRequest struct {
	IDNumber string                `form:"id_number" binding:"required"`
	Selfie   *multipart.FileHeader `form:"selfie" binding:"required"`
}
