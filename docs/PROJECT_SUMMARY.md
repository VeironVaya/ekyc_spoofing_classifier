# Liveness Detection Service — Project Summary

## 1. Scope & positioning

- **Not** a full e-KYC system. This is a **liveness detection / presentation attack detection (PAD) module** — one component of an e-KYC pipeline, applied to a banking registration flow.
- Deliberately dropped from scope: OCR/document verification, face matching, video/motion-based (challenge-response) liveness. Kept the project focused and honestly scoped for an internship deliverable.
- **The innovation**: tie spoof attempts to a hashed identity, build a memory of attempt history across sessions, and apply a **graduated response** rather than a hard block on the first flagged attempt.

## 2. The model

- File: `model_fold_0.pth`, ~188.8 MB.
- Likely a full training checkpoint (may include optimizer state) or a ResNet-scale architecture — **needs verifying**: single model object vs. `state_dict`.
- Task: single-image classification into 6 classes — `fake_printed`, `fake_mask`, `fake_mannequin`, `realperson`, `fake_screen`, `fake_unknown`.
- One image per inference. No video, no motion/temporal analysis.
- **Action item**: inspect the checkpoint (`torch.load()` + check `type()`) before writing the loader, to know whether to load directly or reconstruct the model class first.

## 3. Pipeline (per registration attempt)

1. Frontend submits ID number + selfie image.
2. Go/Gin backend receives the request.
3. Go backend calls the Python inference microservice (internal only) with the image.
4. Python service runs the model, returns JSON: `predicted_class`, `confidence`, `is_live`, `all_scores`.
5. Go backend hashes the ID number (SHA-256).
6. If a spoof is detected (anything other than `realperson`): the selfie is saved to local filesystem storage as evidence. Genuine attempts do **not** get an image saved.
7. Attempt is logged to MySQL: `id_number_hash`, `predicted_class`, `confidence`, `image_path` (nullable), `timestamp`.
8. Risk lookup: query prior spoof-attempt count for this `id_number_hash`.
9. Decision logic combines the current result + history → `continue_registration` / `manual_review` / `blocked_flagged` (graduated, never an instant permanent ban).
10. JSON result returned to the frontend.

## 4. Architecture

| Component | Choice | Notes |
|---|---|---|
| Frontend | React static build | |
| Web server | Nginx, **native** on the VM (not Dockerized) | Avoids the earlier Docker networking issue; single public entry point |
| Backend | Go + Gin, Dockerized | Bound to `127.0.0.1:8080` — reachable only via Nginx |
| Model inference | Python microservice (FastAPI-style), Dockerized | Internal only — no host port exposed; reachable only from the backend over the Docker network |
| Database | MySQL, Dockerized (or native) | Attempt log + risk data |
| Image storage | Local filesystem, Docker volume-mounted, date-subfoldered | Stores images only for flagged/spoofed attempts |
| Image access | Auth-gated admin endpoint | Never served directly by Nginx |
| CI/CD | Postponed | Manual `git pull` + build script for now; GitHub Actions workflow sketched for later |

**Request flow**: Browser → Nginx (native) → Go/Gin backend (Docker) → [Python inference service (Docker, internal)] + [MySQL (Docker)] → decision logic (in Go) → JSON response.

## 5. Folder structure

Repo root — three deployable units side by side:

```
ekyc-liveness-project/
|-- backend/        Go + Gin API (Dockerized)
|-- inference/       Python model service (Dockerized, internal-only)
|-- frontend/         React app (built locally/CI, served by native Nginx)
|-- nginx/
|   |-- liveness.conf   reverse proxy config (see section 4)
|-- docker-compose.yml    backend + inference + mysql
|-- README.md
```

**`backend/`** — your existing Go convention, filled in for this project:

```
backend/
|-- cmd/
|   |-- main.go                        entrypoint: builds config, connects DB, starts Gin router
|-- internal/
|   |-- app/
|   |   |-- controllers/
|   |   |   |-- liveness_controller.go     POST /verify, GET /admin/attempts/:id/image
|   |   |-- dtos/
|   |   |   |-- verify_request.go          incoming multipart fields (id_number, selfie)
|   |   |   |-- verify_response.go         outgoing JSON (liveness result + decision)
|   |   |-- models/
|   |   |   |-- spoof_attempt.go           DB entity: IDNumberHash, PredictedClass, Confidence, ImagePath, CreatedAt
|   |   |-- repositories/
|   |   |   |-- spoof_attempt_repository.go   LogAttempt(), GetPriorAttempts()
|   |   |-- routes/
|   |   |   |-- liveness_routes.go         route registration, wires auth middleware on admin route
|   |   |-- services/
|   |   |   |-- inference_service.go       CallInferenceService() — HTTP call to the Python container
|   |   |   |-- decision_service.go        Decide() — graduated decision logic
|   |   |-- utils/
|   |       |-- hash.go                    HashIDNumber() (SHA-256)
|   |       |-- image_storage.go           SaveEvidenceImage()
|   |-- config/
|       |-- database.go                    MySQL connection setup
|       |-- firebase.go                    keep only if this project actually needs it, else drop
|-- .dockerignore
|-- Dockerfile
|-- go.mod
|-- go.sum
|-- readme.md
```

**`inference/`** — new addition, the Python model-serving microservice, kept as its own deployable unit:

```
inference/
|-- app/
|   |-- main.py             FastAPI app, loads model once at startup
|   |-- model_loader.py     load_model() — handles checkpoint vs state_dict
|   |-- preprocess.py       image transform pipeline (must match training exactly)
|   |-- schemas.py          Pydantic response model
|-- model/
|   |-- model_fold_0.pth
|-- requirements.txt
|-- Dockerfile
|-- .dockerignore
```

**`frontend/`** — proposed structure, same cleanliness principle applied to React:

```
frontend/
|-- public/
|-- src/
|   |-- components/
|   |   |-- CameraCapture.jsx    selfie capture UI (getUserMedia)
|   |   |-- ResultCard.jsx       shows verification result to the user
|   |-- pages/
|   |   |-- RegistrationPage.jsx
|   |-- services/
|   |   |-- api.js               calls backend /api/verify
|   |-- App.jsx
|   |-- index.js
|-- package.json
|-- .env                          e.g. REACT_APP_API_URL
|-- readme.md
```

## 6. Deployment target

- Azure VM, Docker for backend/inference/DB, native Nginx for frontend + reverse proxy.
- Recommended size: **B2s** (2 vCPU / 4 GB RAM) minimum; **B2ms** (2 vCPU / 8 GB RAM) if you want comfortable memory headroom.
- Budget: ~$49 Azure student credit remaining, expiring in 129 days. For a 2-day run: roughly **$2–4 total** — trivial at this duration.
- Remember to **deallocate (not just shut down)** the VM after use, and set an Azure Cost Management budget alert as a safety net.

## 7. Still to build

1. Confirm `model_fold_0.pth` checkpoint structure → finalize `load_model()` in `inference/app/model_loader.py`.
2. `inference/`: Dockerfile + FastAPI endpoint (internal-only, no host port).
3. `backend/internal/app/controllers/liveness_controller.go` + `services/inference_service.go`.
4. `backend/internal/app/utils/hash.go` + `image_storage.go`.
5. `backend/internal/app/models/spoof_attempt.go` + the MySQL table it maps to.
6. `backend/internal/app/repositories/spoof_attempt_repository.go` — `LogAttempt()` / `GetPriorAttempts()`.
7. `backend/internal/app/services/decision_service.go` — `Decide()` graduated logic.
8. Auth-gated admin route in `liveness_routes.go` for viewing evidence images.
9. `docker-compose.yml` wiring backend + inference + MySQL together.
10. `nginx/liveness.conf` — serve frontend + reverse-proxy to backend.
11. Deploy script (`git pull` + `npm build` + `rsync`/`scp` to VM) — CI/CD automation deferred.

## 8. Explicitly out of scope (worth stating in your report)

- OCR / document verification
- Face matching
- Video / challenge-response liveness
- Full regulatory compliance machinery (retention policy, consent flows, formal audit format) — acknowledge it exists in real systems, but correctly out of scope here
