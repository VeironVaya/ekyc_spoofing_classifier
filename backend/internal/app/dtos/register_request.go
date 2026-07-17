package dtos

import "mime/multipart"

type RegisterRequest struct {
	IDCard *multipart.FileHeader `form:"id_card" binding:"required"`
	Selfie *multipart.FileHeader `form:"selfie" binding:"required"`
	// User-confirmed field values from the review form - take precedence over
	// raw OCR output, which is only a best-effort starting point. Optional so
	// direct API callers that skip the preview/confirm step still work,
	// falling back to whatever OCR extracted.
	NIK  string `form:"nik"`
	Name string `form:"name"`
	DOB  string `form:"dob"`
}
