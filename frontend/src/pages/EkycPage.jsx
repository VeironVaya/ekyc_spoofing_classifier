import { useState } from "react";
import CameraCapture from "../components/CameraCapture";
import Header from "../components/Header";
import Alert from "../components/Alert";
import Spinner from "../components/Spinner";
import { previewEkyc, registerEkyc } from "../services/api";

const DECISION_LABELS = {
  approved: "Approved",
  manual_review: "Manual review needed",
  rejected_face_mismatch: "Rejected - face does not match ID",
  rejected_spoof: "Rejected - spoof detected",
  rejected_manual: "Rejected",
};

const NIK_PATTERN = /^\d{16}$/;

export default function EkycPage() {
  const [idCardFile, setIdCardFile] = useState(null);
  const [idCardPreview, setIdCardPreview] = useState(null);
  const [selfieBlob, setSelfieBlob] = useState(null);
  const [selfiePreview, setSelfiePreview] = useState(null);

  // capture -> review (editable form, prefilled from OCR) -> result
  const [stage, setStage] = useState("capture");
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

  const handleIdCardChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file for the ID card.");
      return;
    }
    setIdCardFile(file);
    setIdCardPreview(URL.createObjectURL(file));
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

  const handleExtract = async (e) => {
    e.preventDefault();
    if (loading) return;
    if (!idCardFile) {
      setError("Upload an ID card photo first.");
      return;
    }
    if (!selfieBlob) {
      setError("Capture a selfie first.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await previewEkyc(idCardFile, selfieBlob);
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

  const handleConfirm = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const data = await registerEkyc(idCardFile, selfieBlob, fields);
      setResult(data);
      setStage("result");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStartOver = () => {
    setIdCardFile(null);
    setIdCardPreview(null);
    setSelfieBlob(null);
    setSelfiePreview(null);
    resetDownstream();
  };

  const nikLooksValid = fields.nik === "" || NIK_PATTERN.test(fields.nik);

  return (
    <div className="page-shell">
      <Header current="ekyc" />
      <div className="page-body">
        <div className="registration-page">
          <h1>eKYC Registration (Demo)</h1>
          <p className="ekyc-subtitle">
            ID document OCR + face match are demo-grade, not production accuracy. You'll get a
            chance to review and correct the extracted fields before submitting.
          </p>

          {stage === "capture" && (
            <form onSubmit={handleExtract}>
              <label>
                ID Card Photo
                <input type="file" accept="image/*" onChange={handleIdCardChange} disabled={loading} />
              </label>

              {idCardPreview && (
                <div className="selfie-preview">
                  <img src={idCardPreview} alt="ID card" />
                </div>
              )}

              {!selfiePreview ? (
                <CameraCapture onCapture={handleSelfieCapture} />
              ) : (
                <div className="selfie-preview">
                  <img src={selfiePreview} alt="Captured selfie" />
                  <button type="button" className="secondary" onClick={handleRetakeSelfie} disabled={loading}>
                    Retake
                  </button>
                </div>
              )}

              <Alert type="error">{error}</Alert>

              <button type="submit" disabled={loading}>
                {loading && <Spinner />}
                {loading ? "Checking..." : "Extract & Review"}
              </button>
            </form>
          )}

          {stage === "review" && checkResult && (
            <div className="ekyc-review">
              <div className="ekyc-section">
                <h4>Liveness</h4>
                <p>
                  <span
                    className={`badge ${checkResult.is_live ? "badge-success" : "badge-danger"}`}
                  >
                    {checkResult.is_live ? "Live" : "Spoof"}
                  </span>{" "}
                  {checkResult.liveness_predicted_class} (
                  {(checkResult.liveness_confidence * 100).toFixed(1)}%)
                </p>
              </div>

              <div className="ekyc-section">
                <h4>Face Match</h4>
                <p>
                  <span
                    className={`badge ${checkResult.face_match_verified ? "badge-success" : "badge-danger"}`}
                  >
                    {checkResult.face_match_verified ? "Matched" : "Not matched"}
                  </span>
                  {checkResult.face_match_distance != null &&
                    ` distance ${checkResult.face_match_distance.toFixed(3)}`}
                </p>
                {checkResult.face_match_error && (
                  <p className="form-error">{checkResult.face_match_error}</p>
                )}
              </div>

              <label>
                NIK
                <input
                  type="text"
                  value={fields.nik}
                  onChange={(e) => setFields((f) => ({ ...f, nik: e.target.value }))}
                  placeholder="16-digit NIK"
                  disabled={loading}
                />
                <span className="field-hint">
                  {nikLooksValid
                    ? "OCR best-effort - double check every digit against the card."
                    : "Must be exactly 16 digits to auto-approve, otherwise this goes to manual review."}
                </span>
              </label>
              <label>
                Name
                <input
                  type="text"
                  value={fields.name}
                  onChange={(e) => setFields((f) => ({ ...f, name: e.target.value }))}
                  placeholder="Full name"
                  disabled={loading}
                />
              </label>
              <label>
                Date of birth
                <input
                  type="text"
                  value={fields.dob}
                  onChange={(e) => setFields((f) => ({ ...f, dob: e.target.value }))}
                  placeholder="DD-MM-YYYY"
                  disabled={loading}
                />
              </label>

              <details>
                <summary>Raw OCR text</summary>
                <pre className="ekyc-raw-text">{checkResult.raw_ocr_text}</pre>
              </details>

              <Alert type="error">{error}</Alert>

              <div className="ekyc-review-actions">
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setStage("capture")}
                  disabled={loading}
                >
                  Back
                </button>
                <button type="button" onClick={handleConfirm} disabled={loading}>
                  {loading && <Spinner />}
                  {loading ? "Submitting..." : "Complete Registration"}
                </button>
              </div>
            </div>
          )}

          {stage === "result" && result && (
            <div className={`result-card ekyc-result ekyc-${result.decision}`}>
              <h3>{DECISION_LABELS[result.decision] || result.decision}</h3>

              <div className="ekyc-section">
                <h4>Liveness</h4>
                <p>
                  {result.liveness_predicted_class} ({(result.liveness_confidence * 100).toFixed(1)}
                  %)
                </p>
              </div>

              <div className="ekyc-section">
                <h4>Face Match</h4>
                <p>
                  {result.face_match_verified ? "Matched" : "Not matched"}
                  {result.face_match_distance != null &&
                    ` - distance ${result.face_match_distance.toFixed(3)}`}
                </p>
                {result.face_match_error && <p className="form-error">{result.face_match_error}</p>}
              </div>

              <div className="ekyc-section">
                <h4>Registered ID Fields</h4>
                <p>NIK: {result.extracted_nik || "not provided"}</p>
                <p>Name: {result.extracted_name || "not provided"}</p>
                <p>Date of birth: {result.extracted_dob || "not provided"}</p>
                <details>
                  <summary>Raw OCR text</summary>
                  <pre className="ekyc-raw-text">{result.raw_ocr_text}</pre>
                </details>
              </div>

              <button type="button" onClick={handleStartOver}>
                Start a new registration
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
