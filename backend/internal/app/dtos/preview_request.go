package dtos

import "mime/multipart"

type PreviewRequest struct {
	IDCard *multipart.FileHeader `form:"id_card" binding:"required"`
	Selfie *multipart.FileHeader `form:"selfie" binding:"required"`
}
