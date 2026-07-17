# eKYC Demo — Liveness Detection, OCR & Face Match

A demo electronic KYC (know-your-customer) pipeline for a banking registration flow, built as an internship project. It started as a single-purpose **liveness detection (anti-spoofing) service** and grew into a small end-to-end eKYC demo: capture a selfie, catch spoof attempts, read an ID card, and match the face on the card against the person holding it — with a human always able to review and correct what the machine got wrong.

This is a demo, not a production KYC system. OCR and face-matching are best-effort, not certified accuracy — see [Limitations](#limitations--honest-scope) before assuming otherwise.

## Why this exists

Most anti-spoofing demos stop at "photo of a photo → reject." Two things this project does differently:

1. **Graduated response instead of a hard block.** A single flagged attempt doesn't ban anyone. Spoof attempts are tied to a hashed ID number, and the decision escalates only as repeat attempts accumulate (`continue_registration` → `manual_review` → `blocked_flagged`). One bad photo shouldn't lock a genuine user out of their own registration.
2. **OCR/face-match feed a human, not a black box.** ID card OCR and face-matching are both genuinely unreliable at demo-grade accuracy — trusting them blindly to auto-approve or auto-reject a registration is the wrong call. So the eKYC flow runs the checks, shows the extracted NIK/name/DOB to the user in an editable form for correction, and only *then* re-verifies liveness and face-match server-side (never trusting a client-supplied "it already checked out") before logging a final decision. Getting a field wrong routes to manual review instead of silently completing with bad data.

## What it does

- **Liveness check** (`/verify`): single selfie in, 6-way classification out (`realperson` vs. four spoof types: printed photo, mask, mannequin, screen-replay, plus an `unknown` bucket). Genuine attempts leave no image on disk — only flagged spoof attempts are saved as evidence, by design.
- **Full eKYC registration** (`/ekyc`): ID card photo + selfie in. Runs liveness, OCR (NIK / name / date of birth), and face match between the ID photo and the selfie, concurrently. Shows you the extracted fields to review/correct, then submits.
- **Admin dashboard** (`/admin`): API-key-gated log of every liveness attempt and every eKYC registration, with evidence images, and the ability to manually approve or reject a registration after eyeballing the documents yourself.
- **phpMyAdmin**: optional web UI onto the underlying MySQL database for poking at the raw data.

## Architecture

```
Browser → Nginx (native, prod) or CRA dev server (local)
             │
             ▼
     Go + Gin backend (Docker)  ──HTTP──►  Python + FastAPI inference service (Docker, internal-only)
             │                                    - ConvNeXt-Small liveness classifier (PyTorch)
             ▼                                    - Tesseract OCR (ID field extraction)
        MySQL (Docker)                            - DeepFace / ArcFace (face match)
```

| Layer | Stack | Notes |
|---|---|---|
| Frontend | React (CRA) | Served by native Nginx in prod, not Dockerized |
| Backend | Go + Gin | Layered `controllers → services → repositories`; only this service talks to MySQL and the inference service |
| Inference | Python + FastAPI | **Internal-only** — no host-exposed port, reachable only from the backend over the Docker network |
| Database | MySQL 8 | Two tables: `spoof_attempts` (liveness-only flow) and `registrations` (eKYC flow) |
| Model | `model_fold_0.pth` (ConvNeXt-Small, `timm`) | Single image in, 6-class softmax out |

Deployment target is a single Azure VM: Docker for backend/inference/MySQL, native Nginx as the only public entry point reverse-proxying to the backend.

## Notable design decisions

- **Privacy-by-design evidence retention diverges by flow.** `/verify` only ever saves an image for a *flagged* attempt — a genuine user's selfie never touches disk. `/register` saves both images for every attempt regardless of outcome, since a KYC registration record is expected to retain what was submitted. This is intentional, not an inconsistency.
- **ID numbers are never stored in plaintext.** Only a SHA-256 hash is persisted; raw ID numbers are never logged.
- **Evidence images are never served as static files.** They're only reachable through an auth-gated `GET .../:id/image` route — Nginx never serves the upload directory directly.
- **OCR fails safe, not confidently wrong.** Early iterations of the NIK extractor occasionally stitched together a plausible-looking-but-wrong 16-digit number from noise elsewhere on the page. That's worse than admitting uncertainty, so extraction now either returns a clearly-a-guess value scoped to the actual labeled field, or nothing at all — and either way, the human reviewing the form has the final say before anything is saved.
- **Admin overrides are auditable.** A registration manually rejected by an admin is logged as `rejected_manual`, kept distinct from the automated `rejected_spoof` / `rejected_face_mismatch` reasons, so the log always shows whether a decision was a human call or a machine one.

## Running it

**Full stack (backend + inference + MySQL + phpMyAdmin):**
```
docker compose up -d
```
- Backend: `http://localhost:8080`
- phpMyAdmin: `http://localhost:8081` (log in with `DB_USER`/`DB_PASSWORD` or `root`/`MYSQL_ROOT_PASSWORD` from `.env`)
- MySQL: exposed on `3306` for any client

**Frontend (not Dockerized):**
```
cd frontend && npm start
```
Runs at `http://localhost:3000` — `/` for the simple liveness check, `/ekyc` for the full demo, `/admin` for the dashboard (needs `ADMIN_API_KEY` from `.env`).

**Backend alone, without Docker:**
```
cd backend && go run cmd/main.go
```

## Limitations & honest scope

- OCR and face-match accuracy are demo-grade (plain Tesseract, ArcFace with no fine-tuning) — not a certified-accuracy KYC pipeline, and not claimed to be one.
- No video or challenge-response liveness — the model is single-image only.
- No cross-check against an actual government ID database — a NIK is only validated for *format* (16 digits), not *existence*.
- No CI/CD — deploys are manual (`git pull` + build + `rsync` to the VM) for now.
