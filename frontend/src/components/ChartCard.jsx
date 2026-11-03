import { ResponsiveContainer } from "recharts";

export default function ChartCard({ title, empty, children }) {
  return (
    <div className="chart-card">
      <h4>{title}</h4>
      {empty ? (
        <p className="empty-state">{empty}</p>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          {children}
        </ResponsiveContainer>
      )}
    </div>
  );
}
