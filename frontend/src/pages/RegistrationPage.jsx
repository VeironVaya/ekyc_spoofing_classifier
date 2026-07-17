import { useState } from "react";
import CameraCapture from "../components/CameraCapture";
import ResultCard from "../components/ResultCard";
import Header from "../components/Header";
import Alert from "../components/Alert";
import Spinner from "../components/Spinner";
import { verifySelfie } from "../services/api";

export default function RegistrationPage() {
  const [idNumber, setIdNumber] = useState("");
  const [selfieBlob, setSelfieBlob] = useState(null);
  const [selfiePreview, setSelfiePreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleCapture = (blob) => {
    setSelfieBlob(blob);
    setSelfiePreview(URL.createObjectURL(blob));
    setResult(null);
    setError(null);
  };

  const handleRetake = () => {
    setSelfieBlob(null);
    setSelfiePreview(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    if (!idNumber.trim()) {
      setError("Enter an ID number first.");
      return;
    }
    if (!selfieBlob) {
      setError("Capture a selfie first.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await verifySelfie(idNumber.trim(), selfieBlob);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <Header current="liveness" />
      <div className="page-body">
        <div className="registration-page">
          <h1>Registration - Liveness Check</h1>

          <form onSubmit={handleSubmit}>
            <label>
              ID Number
              <input
                type="text"
                value={idNumber}
                onChange={(e) => setIdNumber(e.target.value)}
                placeholder="Enter your ID number"
                disabled={loading}
              />
            </label>

            {!selfiePreview ? (
              <CameraCapture onCapture={handleCapture} />
            ) : (
              <div className="selfie-preview">
                <img src={selfiePreview} alt="Captured selfie" />
                <button type="button" className="secondary" onClick={handleRetake} disabled={loading}>
                  Retake
                </button>
              </div>
            )}

            <Alert type="error">{error}</Alert>

            <button type="submit" disabled={loading}>
              {loading && <Spinner />}
              {loading ? "Verifying..." : "Submit"}
            </button>
          </form>

          <ResultCard result={result} />
        </div>
      </div>
    </div>
  );
}
