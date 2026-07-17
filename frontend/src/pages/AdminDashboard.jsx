import { useCallback, useState } from "react";
import Header from "../components/Header";
import Alert from "../components/Alert";
import Spinner from "../components/Spinner";
import {
  fetchAttempts,
  fetchAttemptImageUrl,
  fetchRegistrations,
  fetchRegistrationImageUrl,
  updateRegistrationDecision,
} from "../services/api";

const ATTEMPT_DECISION_LABELS = {
  continue_registration: "Continue",
  manual_review: "Manual review",
  blocked_flagged: "Blocked",
};

const ATTEMPT_DECISION_BADGE = {
  continue_registration: "badge-success",
  manual_review: "badge-warning",
  blocked_flagged: "badge-danger",
};

const REGISTRATION_DECISION_LABELS = {
  approved: "Approved",
  manual_review: "Manual review",
  rejected_face_mismatch: "Face mismatch",
  rejected_spoof: "Spoof",
  rejected_manual: "Rejected (manual)",
};

const REGISTRATION_DECISION_BADGE = {
  approved: "badge-success",
  manual_review: "badge-warning",
  rejected_face_mismatch: "badge-danger",
  rejected_spoof: "badge-danger",
  rejected_manual: "badge-danger",
};

export default function AdminDashboard() {
  const [apiKey, setApiKey] = useState("");
  const [authed, setAuthed] = useState(false);
  const [tab, setTab] = useState("attempts");
  const [attempts, setAttempts] = useState([]);
  const [registrations, setRegistrations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [imageLoadingId, setImageLoadingId] = useState(null);
  const [reviewingId, setReviewingId] = useState(null);

  const loadAll = useCallback(async (key) => {
    if (!key.trim()) {
      setError("Enter the admin API key first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [attemptsData, registrationsData] = await Promise.all([
        fetchAttempts(key),
        fetchRegistrations(key),
      ]);
      setAttempts(attemptsData || []);
      setRegistrations(registrationsData || []);
      setAuthed(true);
    } catch (err) {
      setError(err.message);
      setAuthed(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleUnlock = (e) => {
    e.preventDefault();
    if (loading) return;
    loadAll(apiKey);
  };

  const handleViewAttemptImage = async (id) => {
    if (imageLoadingId) return;
    setError(null);
    setImageLoadingId(`attempt-${id}`);
    try {
      const url = await fetchAttemptImageUrl(id, apiKey);
      setImagePreview({ id, url });
    } catch (err) {
      setError(err.message);
    } finally {
      setImageLoadingId(null);
    }
  };

  const handleViewRegistrationImage = async (id, type) => {
    if (imageLoadingId) return;
    setError(null);
    setImageLoadingId(`${id}-${type}`);
    try {
      const url = await fetchRegistrationImageUrl(id, type, apiKey);
      setImagePreview({ id: `${id}-${type}`, url });
    } catch (err) {
      setError(err.message);
    } finally {
      setImageLoadingId(null);
    }
  };

  const handleReviewDecision = async (id, decision) => {
    if (reviewingId) return;
    if (decision === "rejected_manual") {
      const confirmed = window.confirm(
        "Reject this registration? This overrides the automated decision and is visible in the log."
      );
      if (!confirmed) return;
    }
    setError(null);
    setReviewingId(id);
    try {
      await updateRegistrationDecision(id, decision, apiKey);
      setRegistrations((prev) => prev.map((r) => (r.id === id ? { ...r, decision } : r)));
    } catch (err) {
      setError(err.message);
    } finally {
      setReviewingId(null);
    }
  };

  if (!authed) {
    return (
      <div className="page-shell">
        <Header current="admin" />
        <div className="page-body">
          <div className="admin-dashboard">
            <h1>Admin Dashboard</h1>
            <form onSubmit={handleUnlock}>
              <label>
                Admin API Key
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter ADMIN_API_KEY"
                  disabled={loading}
                />
              </label>
              <Alert type="error">{error}</Alert>
              <button type="submit" disabled={loading}>
                {loading && <Spinner />}
                {loading ? "Checking..." : "Unlock"}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <Header current="admin" />
      <div className="page-body">
        <div className="admin-dashboard">
          <div className="admin-header">
            <h1>{tab === "attempts" ? "Attempt Log" : "eKYC Registration Log"}</h1>
            <div className="admin-header-actions">
              <button type="button" onClick={() => loadAll(apiKey)} disabled={loading}>
                {loading && <Spinner />}
                {loading ? "Refreshing..." : "Refresh"}
              </button>
            </div>
          </div>

          <div className="admin-tabs">
            <button
              type="button"
              className={tab === "attempts" ? "active" : ""}
              onClick={() => setTab("attempts")}
            >
              Liveness Attempts ({attempts.length})
            </button>
            <button
              type="button"
              className={tab === "registrations" ? "active" : ""}
              onClick={() => setTab("registrations")}
            >
              eKYC Registrations ({registrations.length})
            </button>
          </div>

          <Alert type="error">{error}</Alert>

          {tab === "attempts" &&
            (attempts.length === 0 && !loading ? (
              <p className="empty-state">No attempts logged yet.</p>
            ) : (
              <div className="attempts-table-wrapper">
                <table className="attempts-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>ID Hash</th>
                      <th>Predicted Class</th>
                      <th>Confidence</th>
                      <th>Decision</th>
                      <th>Evidence</th>
                      <th>Timestamp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attempts.map((a) => (
                      <tr key={a.id} className={a.is_live ? "row-live" : "row-spoof"}>
                        <td>{a.id}</td>
                        <td className="hash-cell" title={a.id_number_hash}>
                          {a.id_number_hash.slice(0, 12)}...
                        </td>
                        <td>{a.predicted_class}</td>
                        <td>{(a.confidence * 100).toFixed(1)}%</td>
                        <td>
                          <span className={`badge ${ATTEMPT_DECISION_BADGE[a.decision] || "badge-neutral"}`}>
                            {ATTEMPT_DECISION_LABELS[a.decision] || a.decision}
                          </span>
                        </td>
                        <td>
                          {a.has_image ? (
                            <button
                              type="button"
                              onClick={() => handleViewAttemptImage(a.id)}
                              disabled={imageLoadingId === `attempt-${a.id}`}
                            >
                              {imageLoadingId === `attempt-${a.id}` ? <Spinner /> : "View"}
                            </button>
                          ) : (
                            "-"
                          )}
                        </td>
                        <td>{new Date(a.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}

          {tab === "registrations" &&
            (registrations.length === 0 && !loading ? (
              <p className="empty-state">No registrations logged yet.</p>
            ) : (
              <div className="attempts-table-wrapper">
                <table className="attempts-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>NIK Hash</th>
                      <th>Name</th>
                      <th>DOB</th>
                      <th>Liveness</th>
                      <th>Face Match</th>
                      <th>Decision</th>
                      <th>Documents</th>
                      <th>Timestamp</th>
                      <th>Review</th>
                    </tr>
                  </thead>
                  <tbody>
                    {registrations.map((r) => (
                      <tr key={r.id} className={r.decision === "approved" ? "row-live" : "row-spoof"}>
                        <td>{r.id}</td>
                        <td className="hash-cell" title={r.nik_hash}>
                          {r.nik_hash ? `${r.nik_hash.slice(0, 12)}...` : "-"}
                        </td>
                        <td>{r.extracted_name || "-"}</td>
                        <td>{r.extracted_dob || "-"}</td>
                        <td>
                          {r.liveness_predicted_class} ({(r.liveness_confidence * 100).toFixed(0)}%)
                        </td>
                        <td>{r.face_match_verified ? "Matched" : "No match"}</td>
                        <td>
                          <span
                            className={`badge ${REGISTRATION_DECISION_BADGE[r.decision] || "badge-neutral"}`}
                          >
                            {REGISTRATION_DECISION_LABELS[r.decision] || r.decision}
                          </span>
                        </td>
                        <td className="doc-buttons">
                          {r.has_id_card_image && (
                            <button
                              type="button"
                              onClick={() => handleViewRegistrationImage(r.id, "id_card")}
                              disabled={imageLoadingId === `${r.id}-id_card`}
                            >
                              {imageLoadingId === `${r.id}-id_card` ? <Spinner /> : "ID"}
                            </button>
                          )}
                          {r.has_selfie_image && (
                            <button
                              type="button"
                              onClick={() => handleViewRegistrationImage(r.id, "selfie")}
                              disabled={imageLoadingId === `${r.id}-selfie`}
                            >
                              {imageLoadingId === `${r.id}-selfie` ? <Spinner /> : "Selfie"}
                            </button>
                          )}
                        </td>
                        <td>{new Date(r.created_at).toLocaleString()}</td>
                        <td className="doc-buttons">
                          <button
                            type="button"
                            className="success"
                            onClick={() => handleReviewDecision(r.id, "approved")}
                            disabled={reviewingId === r.id}
                          >
                            {reviewingId === r.id ? <Spinner /> : "Approve"}
                          </button>
                          <button
                            type="button"
                            className="danger"
                            onClick={() => handleReviewDecision(r.id, "rejected_manual")}
                            disabled={reviewingId === r.id}
                          >
                            Reject
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}

          {imagePreview && (
            <div className="image-modal" onClick={() => setImagePreview(null)}>
              <img
                src={imagePreview.url}
                alt={`Evidence ${imagePreview.id}`}
                onClick={(e) => e.stopPropagation()}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
