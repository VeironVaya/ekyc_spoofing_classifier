const DECISION_LABELS = {
  continue_registration: "Registration can continue",
  manual_review: "Flagged for manual review",
  blocked_flagged: "Blocked - too many flagged attempts",
};

const DECISION_BADGE = {
  continue_registration: "badge-success",
  manual_review: "badge-warning",
  blocked_flagged: "badge-danger",
};

export default function ResultCard({ result }) {
  if (!result) return null;

  const { predicted_class, confidence, is_live, decision, all_scores } = result;

  return (
    <div className={`result-card ${is_live ? "result-live" : "result-spoof"}`}>
      <h3>
        <span className={`badge ${is_live ? "badge-success" : "badge-danger"}`}>
          {is_live ? "Live" : "Spoof"}
        </span>
        {is_live ? "Live person detected" : "Spoof attempt detected"}
      </h3>
      <p>
        Predicted class: <strong>{predicted_class}</strong>
      </p>
      <p>
        Confidence: <strong>{(confidence * 100).toFixed(1)}%</strong>
      </p>
      <p>
        Decision:{" "}
        <span className={`badge ${DECISION_BADGE[decision] || "badge-neutral"}`}>
          {DECISION_LABELS[decision] || decision}
        </span>
      </p>

      {all_scores && (
        <details>
          <summary>All class scores</summary>
          <ul>
            {Object.entries(all_scores).map(([cls, score]) => (
              <li key={cls}>
                {cls}: {(score * 100).toFixed(1)}%
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
