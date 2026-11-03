import { useState } from "react";
import ImageCapture from "../components/ImageCapture";
import Header from "../components/Header";
import Alert from "../components/Alert";
import Spinner from "../components/Spinner";
import { checkKtpForgery } from "../services/api";
import { qualityRejectMessage } from "../utils/qualityMessages";

const CLASS_CONFIG = {
  real_ktp: {
    label: "Authentic KTP",
    subtitle: "Genuine physical card captured by camera",
    badgeClass: "badge-success",
    color: "#15803d",
    icon: "✓",
    isAuthentic: true,
  },
  fake_screen: {
    label: "Screen Replay Attack",
    subtitle: "KTP displayed on monitor/mobile phone screen (moiré/subpixel)",
    badgeClass: "badge-danger",
    color: "#dc2626",
    icon: "🖥",
    isAuthentic: false,
  },
  fake_print: {
    label: "Paper Printout Attack",
    subtitle: "Physical printout or cardstock cutout (halftone dots/paper fibers)",
    badgeClass: "badge-danger",
    color: "#ea580c",
    icon: "📄",
    isAuthentic: false,
  },
  fake_template: {
    label: "Synthetic Dummy Template",
    subtitle: "Digitally generated synthetic card / vector artifacts",
    badgeClass: "badge-danger",
    color: "#d97706",
    icon: "⚙",
    isAuthentic: false,
  },
  other: {
    label: "Non-KTP Document",
    subtitle: "Invalid card format (SIM driving license, credit card, membership)",
    badgeClass: "badge-danger",
    color: "#7c3aed",
    icon: "✕",
    isAuthentic: false,
  },
};

export default function KtpForgeryPage() {
  const [ktpFile, setKtpFile] = useState(null);
  const [ktpPreview, setKtpPreview] = useState(null);
  const [mockClass, setMockClass] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleCapture = (fileOrBlob) => {
    setKtpFile(fileOrBlob);
    setKtpPreview(URL.createObjectURL(fileOrBlob));
    setResult(null);
    setError(null);
  };

  const handleClear = () => {
    setKtpFile(null);
    setKtpPreview(null);
    setResult(null);
    setError(null);
  };

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!ktpFile || loading) return;

    setLoading(true);
    setError(null);
    try {
      const data = await checkKtpForgery(ktpFile, mockClass);
      if (!data.quality_passed) {
        setError(qualityRejectMessage(data.quality_reject_reason));
        setResult(null);
        return;
      }
      setResult(data);
    } catch (err) {
      setError(err.message || "Failed to analyze document.");
    } finally {
      setLoading(false);
    }
  };

  const predConfig = result?.predicted_class ? CLASS_CONFIG[result.predicted_class] : null;

  return (
    <div className="page-shell">
      <Header current="ktp-forgery" />
      <div className="page-body">
        <div className={result ? "forgery-layout-split" : "registration-page ktp-forgery-card"}>
          <div className="registration-page ktp-forgery-card">
            <span className="mode-pill">Mode 4: Standalone Doc-PAD</span>
            <h1>Indonesian KTP Forgery Detection</h1>
            <p className="ekyc-subtitle">
              Single-image Document Presentation Attack Detection (Doc-PAD). Evaluates whether a captured
              card is an authentic physical KTP, a screen replay, a paper printout, a synthetic render, or a non-KTP card.
            </p>

            <form onSubmit={handleAnalyze}>
              <ImageCapture
                title="Indonesian KTP Card"
                preview={ktpPreview}
                onCapture={handleCapture}
                onClear={handleClear}
                onError={setError}
                disabled={loading}
                defaultMode="upload"
              />

              {/* Simulation selector for pre-training testing */}
              <div className="mock-toggle-box">
                <label htmlFor="mock-select">
                  <strong>Testing Scenario Override:</strong>
                  <span className="hint-text"> (Simulates attack classes while model is training)</span>
                </label>
                <select
                  id="mock-select"
                  value={mockClass}
                  onChange={(e) => setMockClass(e.target.value)}
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

              <button
                type="submit"
                className="primary analyze-btn"
                disabled={!ktpFile || loading}
              >
                {loading && <Spinner />}
                {loading ? "Analyzing Document..." : "Analyze KTP Authenticity"}
              </button>
            </form>
          </div>

          {/* Results Section */}
          {result && (
            <div className="registration-page ktp-forgery-card result-section">
              <h2>Doc-PAD Classification Verdict</h2>

              <div className={`verdict-banner ${predConfig?.isAuthentic ? "banner-pass" : "banner-fail"}`}>
                <div className="verdict-icon">{predConfig?.icon}</div>
                <div className="verdict-details">
                  <span className="verdict-title">{predConfig?.label}</span>
                  <span className="verdict-subtitle">{predConfig?.subtitle}</span>
                </div>
                <div className="verdict-confidence">
                  <span className="conf-value">{(result.confidence * 100).toFixed(1)}%</span>
                  <span className="conf-label">Confidence</span>
                </div>
              </div>

              <div className="engine-badge-bar">
                <span className={`engine-badge ${result.is_dummy ? "badge-heuristic" : "badge-ai"}`}>
                  {result.is_dummy ? "Heuristic Testing Engine" : "ConvNeXt-Small Deep Learning Model"}
                </span>
                <span className="quality-pill">
                  Blur: {result.blur_score.toFixed(1)} | Brightness: {result.brightness_score.toFixed(1)}
                </span>
              </div>

              {/* 5-Class Probability Distribution */}
              <div className="score-bars-container">
                <h3>Softmax Class Probabilities</h3>
                {Object.entries(CLASS_CONFIG).map(([cKey, conf]) => {
                  const score = (result.all_scores?.[cKey] || 0) * 100;
                  const isSelected = result.predicted_class === cKey;
                  return (
                    <div key={cKey} className={`score-bar-row ${isSelected ? "selected-row" : ""}`}>
                      <div className="score-bar-header">
                        <span className="class-label">
                          {conf.icon} {conf.label}
                        </span>
                        <span className="class-pct">{score.toFixed(1)}%</span>
                      </div>
                      <div className="bar-track">
                        <div
                          className="bar-fill"
                          style={{
                            width: `${Math.max(score, 2)}%`,
                            backgroundColor: conf.color,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="security-note">
                <strong>Doc-PAD Safeguard:</strong> Authentic bank onboarding requires genuine physical cards. Screen
                replays, paper cutouts, and synthetic template dummies are rejected by the graduated risk engine.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
