export default function StatTile({ label, value, hint }) {
  return (
    <div className="stat-tile">
      <span className="stat-tile-value">{value}</span>
      <span className="stat-tile-label">{label}</span>
      {hint && <span className="stat-tile-hint">{hint}</span>}
    </div>
  );
}
