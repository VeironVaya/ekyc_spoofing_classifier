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

Deployment target is a single Azure VM: Docker for backend/inference/MySQL, native Nginx as the only public entry point reverse-proxying to the backend.

## Models & inference, in detail

Three separate models run inside the Python inference service (`inference/app/`), each doing one narrow job — no single model tries to do everything.

### 1. Liveness classifier (`model_loader.py`, `preprocess.py`)

- **Architecture**: `convnext_small.fb_in22k_ft_in1k` (ConvNeXt-Small) loaded via `timm`, head replaced for `num_classes=6`.
- **Weights**: `model_fold_0.pth` (~189 MB) — confirmed to be a raw `state_dict` (`torch.save(model.state_dict(), ...)`), not a full checkpoint object, so the loader calls `timm.create_model(..., pretrained=False)` and loads the state dict directly (stripping any `module.` prefix from a DataParallel-trained checkpoint).
- **Classes** (fixed order, must match training): `fake_mannequin`, `fake_mask`, `fake_printed`, `fake_screen`, `fake_unknown`, `realperson`.
- **Preprocessing** (must exactly match training): resize to 256×256 (`cv2.INTER_LINEAR`), BGR→RGB, scale to `[0,1]`, normalize with ImageNet mean/std (`[0.485,0.456,0.406]` / `[0.229,0.224,0.225]`), transpose to `CHW`, single-image batch.
- **Inference**: single forward pass, `softmax` over the 6 logits, `argmax` for the predicted class, `is_live = (predicted_class == "realperson")`.
- **Runtime**: CPU-only PyTorch (`torch==2.5.1` / `torchvision==0.20.1`, installed from the `download.pytorch.org/whl/cpu` index — no CUDA, no GPU, matches the target Azure VM).

### 2. OCR — ID field extraction (`ocr.py`)

Plain Tesseract (`pytesseract`), no layout model, no fine-tuning — deliberately kept simple for a demo, with real effort put into not being *confidently wrong*:

- **Preprocessing**: grayscale → upscale if the image's longer side is under 1800px (small phone photos need more resolution for Tesseract to resolve small print) → bilateral-filter denoise → CLAHE local contrast boost (`clipLimit=2.0`, 8×8 tiles). Deliberately **no hard binarization** (no Otsu/adaptive threshold) — that was tried and benchmarked against a synthetic KTP-style test image, and both thresholding approaches made recognition *worse* than just denoising + contrast-boosting and leaving the image in grayscale, since Tesseract's LSTM engine (`--oem 1`) already does its own adaptive binarization internally.
- **OCR call**: `pytesseract.image_to_string(image, lang="ind+eng", config="--oem 1 --psm 6")` — `ind+eng` because Indonesian KTP field labels (Nama, Tempat/Tgl Lahir, Kewarganegaraan, …) mix with Latin-alphabet/digit content; `--psm 6` treats the card as a single uniform block of text, which matches a KTP's dense label/value layout better than the default automatic page-segmentation mode.
- **NIK extraction**: scoped strictly to the text *after* a `\bNIK\b` label match (word-boundary, so it doesn't false-trigger on substrings). If the raw digit count there isn't exactly 16, a letter/digit confusion map is applied first (`O→0, I/l/i→1, S/s→5, B→8, Z→2, G→6, A→4, T→7, g→9`) — Tesseract frequently swaps these on small print. If it *still* doesn't resolve to a clean 16-digit run, a best-effort guess fills any remaining unrecognized character with `5` as a placeholder, rather than either leaving the field blank or inventing a wrong-looking-plausible number. Earlier iterations without the label-scoping occasionally stitched together a coincidental 16-digit sequence from unrelated noise elsewhere on the page — a wrong-but-confident answer, which is strictly worse for a KYC decision than an honest placeholder the human is expected to correct.
- **Name extraction**: scoped to the text after a `nama` label match; no fuzzy fallback if that label isn't found — an empty field beats a hallucinated name.
- **Date of birth**: a permissive `DD-MM-YYYY`/`DD/MM/YYYY`-shaped regex over the whole raw text.
- Every field (and the full raw OCR text) is surfaced to the user in the review form before it's ever saved — the extraction only has to get the human close enough to fix, not be perfect.

### 3. Face match (`face_match.py`)

- **Model**: `DeepFace.verify(img1_path=id_card_image, img2_path=selfie_image, model_name="ArcFace")` — ArcFace embeddings, cosine-distance comparison against DeepFace's built-in threshold for that model, default (`opencv`) face detector backend.
- **Weights baked into the Docker image at build time** (`RUN python -c "from deepface import DeepFace; DeepFace.build_model('ArcFace')"` in `inference/Dockerfile`) — without this, the ~130 MB ArcFace weights download from GitHub on the *first* request after every container restart (`/root/.deepface` isn't a persisted volume), which was blowing past a naive request timeout. Baking them in means every container starts ready.
- **Failure handling**: if either image has no detectable face, DeepFace raises `ValueError` — caught and turned into a structured `{verified: false, error: "..."}` response instead of a 500.
- **CPU-only TensorFlow**: DeepFace pulls in `tensorflow` as a transitive dependency of `tf-keras` even with `tensorflow-cpu` pinned explicitly (a known pip resolution quirk — both packages end up installed, ~840 MB combined). Left as-is; it works, and the inefficiency is a demo-acceptable tradeoff, not a correctness issue.

### Concurrency

`POST /ekyc-check` runs OCR and face-match **concurrently** (`asyncio.gather` + `asyncio.to_thread`, since both are blocking calls) rather than back-to-back — combined with the baked-in ArcFace weights, this took a full `/register` round trip from potentially hitting a 120-second cold-start ceiling down to roughly 1.5–2 seconds in steady state.

## Decision logic

Two independent decision engines — the liveness-only flow and the eKYC flow are deliberately not the same logic, because they're answering different questions.

**Liveness-only (`decision_service.go`)** — tied to a SHA-256 hash of the submitted ID number, with memory of that hash's prior attempts:

| Current result | Prior spoof attempts (same hashed ID) | Decision |
|---|---|---|
| Genuine (`realperson`) | < 3 | `continue_registration` |
| Genuine (`realperson`) | ≥ 3 | `manual_review` (clean now, but risky history) |
| Spoof | < 3 | `manual_review` |
| Spoof | ≥ 3 | `blocked_flagged` |

**eKYC registration (`ekyc_controller.go`)** — evaluated in order, first match wins:

1. `!is_live` → `rejected_spoof`
2. `!face_match_verified` → `rejected_face_mismatch`
3. Final NIK (OCR value, or the user's corrected one from the review form) doesn't match `^\d{16}$` → `manual_review`
4. Otherwise → `approved`

An admin can override any registration's decision afterward via `PATCH /admin/registrations/:id/decision` to `approved` or `rejected_manual` — logged as `rejected_manual` specifically (not reusing `rejected_spoof`/`rejected_face_mismatch`) so the log always shows whether a rejection was an automated reason or a human call.

## API reference

**Inference service** (internal-only, not reachable outside the Docker network):

| Route | Purpose |
|---|---|
| `GET /health` | liveness probe, reports whether the model loaded |
| `POST /infer` | single selfie → liveness classification |
| `POST /ekyc-check` | ID card + selfie → OCR fields + face-match result (no persistence) |

**Backend** (`http://localhost:8080`):

| Route | Auth | Purpose |
|---|---|---|
| `POST /verify` | none | liveness-only check, logs to `spoof_attempts`, graduated decision |
| `POST /register/preview` | none | runs liveness + OCR + face-match, returns results for review — saves nothing |
| `POST /register` | none | final submit: re-verifies liveness/face-match from the actual images, accepts optional `nik`/`name`/`dob` overrides from the review form, saves both images + logs to `registrations` |
| `GET /admin/attempts` | Bearer `ADMIN_API_KEY` | list liveness attempts |
| `GET /admin/attempts/:id/image` | Bearer `ADMIN_API_KEY` | evidence image (spoof attempts only) |
| `GET /admin/registrations` | Bearer `ADMIN_API_KEY` | list eKYC registrations |
| `GET /admin/registrations/:id/image?type=id_card\|selfie` | Bearer `ADMIN_API_KEY` | registration evidence image |
| `PATCH /admin/registrations/:id/decision` | Bearer `ADMIN_API_KEY` | manually set `decision` to `approved` or `rejected_manual` |

## Notable design decisions

- **Privacy-by-design evidence retention diverges by flow.** `/verify` only ever saves an image for a *flagged* attempt — a genuine user's selfie never touches disk. `/register` saves both images for every attempt regardless of outcome, since a KYC registration record is expected to retain what was submitted. This is intentional, not an inconsistency.
- **ID numbers are never stored in plaintext.** Only a SHA-256 hash is persisted; raw ID numbers are never logged.
- **Evidence images are never served as static files.** They're only reachable through an auth-gated `GET .../:id/image` route — Nginx never serves the upload directory directly.
- **The final `/register` call never trusts the earlier preview.** Liveness and face-match are always re-derived from the actual submitted image bytes at confirm time, even though `/register/preview` already computed them once — a client can't fake having passed the anti-spoof check.

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
