import { useState } from "react";
import ImageCapture from "../components/ImageCapture";
import Header from "../components/Header";
import Alert from "../components/Alert";
import Spinner from "../components/Spinner";
import { previewCompletePipeline, registerCompletePipeline } from "../services/api";
import { qualityRejectMessage } from "../utils/qualityMessages";

const DECISION_LABELS = {
  approved: "Approved",
  manual_review: "Manual Review Needed",
  rejected_face_mismatch: "Rejected - Face Does Not Match ID",
  rejected_spoof: "Rejected - Selfie Spoof Detected",
  rejected_ktp_forgery: "Rejected - KTP Forgery Detected",
  rejected_poor_quality: "Rejected - Quality Gate Failed",
  rejected_manual: "Rejected (Manual)",
};

export function validateNik(nik) {
  if (!nik || typeof nik !== "string") {
    return { valid: false, reason: "NIK is required" };
  }
  const clean = nik.trim();
  if (!/^\d{16}$/.test(clean)) {
    return { valid: false, reason: "NIK must be exactly 16 numeric digits" };
  }
  const prov = parseInt(clean.substring(0, 2), 10);
  if (prov < 11 || prov > 94) {
    return { valid: false, reason: `Invalid province code (${prov})` };
  }
  const day = parseInt(clean.substring(6, 8), 10);
  const month = parseInt(clean.substring(8, 10), 10);
  if (month < 1 || month > 12) {
    return { valid: false, reason: `Invalid birth month (${month})` };
  }
  const isFemale = day > 40;
  const actualDay = isFemale ? day - 40 : day;
  if (actualDay < 1 || actualDay > 31) {
    return { valid: false, reason: `Invalid birth day (${actualDay})` };
  }
  return {
    valid: true,
    gender: isFemale ? "Female" : "Male",
    provinceCode: prov,
    birthDay: actualDay,
    birthMonth: month,
  };
}

export default function CompletePipelinePage() {
  const [idCardFile, setIdCardFile] = useState(null);
  const [idCardPreview, setIdCardPreview] = useState(null);
  const [selfieBlob, setSelfieBlob] = useState(null);
  const [selfiePreview, setSelfiePreview] = useState(null);
  const [mockKtpClass, setMockKtpClass] = useState("");

  const [stage, setStage] = useState("capture"); // capture -> review -> result
  const [checkResult, setCheckResult] = useState(null);
  const [fields, setFields] = useState({ nik: "", name: "", dob: "" });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const resetDownstream = () => {
    setStage("capture");
    setCheckResult(null);
    setResult(null);
    setError(null);
  };

  const handleIdCardCapture = (fileOrBlob) => {
    setIdCardFile(fileOrBlob);
    setIdCardPreview(URL.createObjectURL(fileOrBlob));
    resetDownstream();
  };

  const handleIdCardClear = () => {
    setIdCardFile(null);
    setIdCardPreview(null);
    resetDownstream();
  };

  const handleSelfieCapture = (blob) => {
    setSelfieBlob(blob);
    setSelfiePreview(URL.createObjectURL(blob));
    resetDownstream();
  };

  const handleRetakeSelfie = () => {
    setSelfieBlob(null);
    setSelfiePreview(null);
    resetDownstream();
  };

  const handleStartOver = () => {
    setIdCardFile(null);
    setIdCardPreview(null);
    setSelfieBlob(null);
    setSelfiePreview(null);
    resetDownstream();
  };

  const handleRunPipeline = async (e) => {
    e.preventDefault();
    if (loading) return;
    if (!idCardFile) {
      setError("Upload or capture a KTP card image first.");
      return;
    }
    if (!selfieBlob) {
      setError("Capture a live selfie first.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await previewCompletePipeline(idCardFile, selfieBlob, mockKtpClass);
      if (!data.quality_passed) {
        setError(qualityRejectMessage(data.quality_reject_reason));
        return;
      }
      setCheckResult(data);
      setFields({
        nik: data.extracted_nik || "",
        name: data.extracted_name || "",
        dob: data.extracted_dob || "",
      });
      setStage("review");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmRegister = async (e) => {
    e.preventDefault();
    if (loading) return;

    setLoading(true);
    setError(null);
    try {
      const data = await registerCompletePipeline(idCardFile, selfieBlob, fields);
      setResult(data);
      setStage("result");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const nikValidation = validateNik(fields.nik);
  const ktpIsAuthentic = checkResult?.ktp_forgery?.is_authentic;
  const isKtpSpoofed = checkResult?.ktp_forgery && !checkResult.ktp_forgery.is_authentic;

  return (
    <div className="page-shell">
      <Header current="pipeline" />
      <div className="page-body">
        {stage === "capture" && (
          <div className="registration-page pipeline-card-wide">
            <span className="mode-pill mode-pill-primary">Complete e-KYC Pipeline</span>
            <h1>Bank Onboarding & Anti-Spoofing Pipeline</h1>
            <p className="ekyc-subtitle">
              Integrates KTP Forgery Detection (Doc-PAD), Deterministic NIK Rules, OCR Extraction,
              Live Selfie Liveness, 1:1 ArcFace Biometric Matching, and Graduated Risk Scoring.
            </p>

            <form onSubmit={handleRunPipeline} className="pipeline-form">
              <div className="dual-capture-grid">
                <ImageCapture
                  title="1. Indonesian KTP Card"
                  preview={idCardPreview}
                  onCapture={handleIdCardCapture}
                  onClear={handleIdCardClear}
                  onError={setError}
                  disabled={loading}
                  defaultMode="upload"
                />

                <ImageCapture
                  title="2. Live User Selfie"
                  preview={selfiePreview}
                  onCapture={handleSelfieCapture}
                  onClear={handleRetakeSelfie}
                  onError={setError}
                  disabled={loading}
                  defaultMode="camera"
                />
              </div>

              {/* Testing scenario override */}
              <div className="mock-toggle-box">
                <label htmlFor="pipeline-mock-select">
                  <strong>KTP Doc-PAD Scenario Override:</strong>
                  <span className="hint-text"> (Simulate attack branches while model is training)</span>
                </label>
                <select
                  id="pipeline-mock-select"
                  value={mockKtpClass}
                  onChange={(e) => setMockKtpClass(e.target.value)}
                  disabled={loading}
                >
                  <option value="">Auto (Real Model / Heuristic)</option>
                  <option value="real_ktp">Simulate: Authentic Physical KTP</option>
                  <option value="fake_screen">Simulate: Screen Replay Attack (fake_screen)</option>
                  <option value="fake_print">Simulate: Paper Printout Attack (fake_print)</option>
                  <option value="fake_template">Simulate: Synthetic Dummy Template (fake_template)</option>
                  <option value="other">Simulate: Non-KTP Document (other)</option>
                </select>
              </div>

              <Alert type="error">{error}</Alert>

              <button type="submit" className="primary launch-btn" disabled={loading}>
                {loading && <Spinner />}
                {loading ? "Running 4-Pillar Verification..." : "Run Complete Pipeline"}
              </button>
            </form>
          </div>
        )}

        {stage === "review" && checkResult && (
          <div className="registration-page pipeline-card-wide">
            <span className="mode-pill mode-pill-primary">Mode 3: Security & OCR Review</span>
            <h1>Security Verification & Data Review</h1>
            <p className="ekyc-subtitle">
              Verify the multi-pillar biometric and document signals below before confirming registration.
            </p>

            {/* 4 Pillars Grid */}
            <div className="security-pillars-grid">
              {/* Pillar 1: KTP Doc-PAD */}
              <div className={`pillar-card ${ktpIsAuthentic ? "pillar-pass" : "pillar-fail"}`}>
                <div className="pillar-header">
                  <span className="pillar-tag">Pillar 1: Doc-PAD</span>
                  <span className={`badge ${ktpIsAuthentic ? "badge-success" : "badge-danger"}`}>
                    {ktpIsAuthentic ? "Authentic" : "Doc Spoof"}
                  </span>
                </div>
                <div className="pillar-metric">
                  <strong>{checkResult.ktp_forgery?.predicted_class || "N/A"}</strong>
                  <span className="metric-sub">
                    Confidence: {((checkResult.ktp_forgery?.confidence || 0) * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="pillar-desc">
                  {ktpIsAuthentic
                    ? "Genuine physical card verified."
                    : "Document presentation attack detected."}
                </p>
              </div>

              {/* Pillar 2: Deterministic NIK */}
              <div className={`pillar-card ${nikValidation.valid ? "pillar-pass" : "pillar-warn"}`}>
                <div className="pillar-header">
                  <span className="pillar-tag">Pillar 2: NIK Rules</span>
                  <span className={`badge ${nikValidation.valid ? "badge-success" : "badge-warning"}`}>
                    {nikValidation.valid ? "Valid NIK" : "Needs Review"}
                  </span>
                </div>
                <div className="pillar-metric">
                  <strong>{fields.nik || "Not Detected"}</strong>
                  <span className="metric-sub">
                    {nikValidation.valid
                      ? `Prov: ${nikValidation.provinceCode} | Gender: ${nikValidation.gender}`
                      : nikValidation.reason}
                  </span>
                </div>
                <p className="pillar-desc">
                  {nikValidation.valid
                    ? `Indonesian 16-digit structure and DOB (${nikValidation.birthDay}/${nikValidation.birthMonth}) verified.`
                    : "Indonesian NIK requires 16 numeric digits with valid province & DOB checksum."}
                </p>
              </div>

              {/* Pillar 3: Selfie Liveness */}
              <div className={`pillar-card ${checkResult.is_live ? "pillar-pass" : "pillar-fail"}`}>
                <div className="pillar-header">
                  <span className="pillar-tag">Pillar 3: Face Liveness</span>
                  <span className={`badge ${checkResult.is_live ? "badge-success" : "badge-danger"}`}>
                    {checkResult.is_live ? "Live Person" : "Selfie Spoof"}
                  </span>
                </div>
                <div className="pillar-metric">
                  <strong>{checkResult.liveness_predicted_class || "N/A"}</strong>
                  <span className="metric-sub">
                    Confidence: {(checkResult.liveness_confidence * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="pillar-desc">
                  {checkResult.is_live ? "Live human presence confirmed." : "Presentation attack detected."}
                </p>
              </div>

              {/* Pillar 4: Face Match */}
              <div className={`pillar-card ${checkResult.face_match_verified ? "pillar-pass" : "pillar-fail"}`}>
                <div className="pillar-header">
                  <span className="pillar-tag">Pillar 4: Face Match</span>
                  <span className={`badge ${checkResult.face_match_verified ? "badge-success" : "badge-danger"}`}>
                    {checkResult.face_match_verified ? "Matched" : "Mismatch"}
                  </span>
                </div>
                <div className="pillar-metric">
                  <strong>ArcFace 1:1</strong>
                  <span className="metric-sub">
                    {checkResult.face_match_distance != null
                      ? `Distance: ${checkResult.face_match_distance.toFixed(3)}`
                      : "Distance: N/A"}
                  </span>
                </div>
                <p className="pillar-desc">
                  {checkResult.face_match_verified
                    ? "KTP portrait matches selfie."
                    : "Face does not match card photo."}
                </p>
              </div>
            </div>

            {/* Spoof Alert Warning */}
            {isKtpSpoofed && (
              <div className="security-alert-box alert-danger">
                <strong>Warning:</strong> The KTP card was flagged as a presentation attack (
                <code>{checkResult.ktp_forgery.predicted_class}</code>). Submitting will trigger an automatic
                high-risk escalation in the graduated decision engine.
              </div>
            )}

            {/* OCR Form Fields */}
            <div className="fields-edit-card">
              <h3>Extracted KTP Fields (Review & Correct)</h3>
              <div className="form-row">
                <label>
                  NIK (National ID Number)
                  <input
                    type="text"
                    value={fields.nik}
                    onChange={(e) => setFields((f) => ({ ...f, nik: e.target.value }))}
                    placeholder="16-digit NIK"
                    disabled={loading}
                  />
                </label>
                <label>
                  Full Name
                  <input
                    type="text"
                    value={fields.name}
                    onChange={(e) => setFields((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Full name as printed on KTP"
                    disabled={loading}
                  />
                </label>
                <label>
                  Date of Birth
                  <input
                    type="text"
                    value={fields.dob}
                    onChange={(e) => setFields((f) => ({ ...f, dob: e.target.value }))}
                    placeholder="DD-MM-YYYY"
                    disabled={loading}
                  />
                </label>
              </div>

              <details className="ocr-details">
                <summary>View Raw Tesseract OCR Output</summary>
                <pre>{checkResult.raw_ocr_text || "(empty)"}</pre>
              </details>
            </div>

            <Alert type="error">{error}</Alert>

            <div className="review-actions">
              <button type="button" className="secondary" onClick={handleStartOver} disabled={loading}>
                Recapture
              </button>
              <button type="button" className="primary" onClick={handleConfirmRegister} disabled={loading}>
                {loading && <Spinner />}
                {loading ? "Confirming..." : "Confirm & Complete Onboarding"}
              </button>
            </div>
          </div>
        )}

        {stage === "result" && result && (
          <div className="registration-page pipeline-card-wide pipeline-result-card">
            <div className="result-header">
              <h2>Onboarding Result</h2>
              <span className={`decision-pill pill-${result.decision}`}>
                {DECISION_LABELS[result.decision] || result.decision}
              </span>
            </div>

            <div className="result-summary-grid">
              <div className="summary-item">
                <span className="summary-label">Registration ID</span>
                <span className="summary-val">{result.id || "N/A"}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Risk Level</span>
                <span className="summary-val">{result.risk_level || "Standard"}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Decision</span>
                <span className="summary-val">{DECISION_LABELS[result.decision] || result.decision}</span>
              </div>
            </div>

            <button type="button" className="primary" onClick={handleStartOver}>
              New Registration
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
