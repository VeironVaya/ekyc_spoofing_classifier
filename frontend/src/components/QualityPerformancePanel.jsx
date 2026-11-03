import { useMemo } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import StatTile from "./StatTile";
import ChartCard from "./ChartCard";
import { CHART_COLORS } from "../utils/chartColors";

const QUALITY_BIN_COUNT = 8;
const SCORE_BIN_SIZE = 0.1;

function isNumber(value) {
  return typeof value === "number";
}

function binByRange(entries, binCount) {
  if (entries.length === 0) return [];
  const values = entries.map((e) => e.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const binSize = (max - min || 1) / binCount;
  const bins = Array.from({ length: binCount }, (_, i) => ({
    range: `${Math.round(min + i * binSize)}-${Math.round(min + (i + 1) * binSize)}`,
  }));
  for (const { value, source } of entries) {
    const idx = Math.min(binCount - 1, Math.floor((value - min) / binSize));
    bins[idx][source] = (bins[idx][source] || 0) + 1;
  }
  return bins;
}

// Confidence is naturally bounded [0, 1], unlike blur/brightness - fixed bin
// edges keep this comparable across refreshes instead of rescaling every time.
function binFixedUnitRange(entries, binSize) {
  const binCount = Math.ceil(1 / binSize);
  const bins = Array.from({ length: binCount }, (_, i) => ({
    range: `${(i * binSize).toFixed(1)}-${((i + 1) * binSize).toFixed(1)}`,
  }));
  for (const { value, source } of entries) {
    const idx = Math.min(binCount - 1, Math.max(0, Math.floor(value / binSize)));
    bins[idx][source] = (bins[idx][source] || 0) + 1;
  }
  return bins;
}

function hourKey(isoString) {
  return isoString.slice(0, 13);
}

function hourLabel(key) {
  return `${key.replace("T", " ")}:00`;
}

function percentile(sortedValues, p) {
  if (sortedValues.length === 0) return 0;
  const idx = Math.min(sortedValues.length - 1, Math.floor(p * sortedValues.length));
  return sortedValues[idx];
}

function average(values) {
  return values.length ? values.reduce((sum, v) => sum + v, 0) / values.length : 0;
}

export default function QualityPerformancePanel({ attempts, registrations, apiRequests }) {
  const overrideStats = useMemo(() => {
    const withAutomated = registrations.filter((r) => r.automated_decision);
    const overridden = withAutomated.filter((r) => r.decision !== r.automated_decision);
    return {
      total: withAutomated.length,
      overridden: overridden.length,
      rate: withAutomated.length ? (overridden.length / withAutomated.length) * 100 : 0,
    };
  }, [registrations]);

  const blurData = useMemo(() => {
    const entries = [
      ...attempts.filter((a) => isNumber(a.blur_score)).map((a) => ({ value: a.blur_score, source: "selfie" })),
      ...registrations
        .filter((r) => isNumber(r.selfie_blur_score))
        .map((r) => ({ value: r.selfie_blur_score, source: "selfie" })),
      ...registrations
        .filter((r) => isNumber(r.id_card_blur_score))
        .map((r) => ({ value: r.id_card_blur_score, source: "id_card" })),
    ];
    return binByRange(entries, QUALITY_BIN_COUNT);
  }, [attempts, registrations]);

  const brightnessData = useMemo(() => {
    const entries = [
      ...attempts
        .filter((a) => isNumber(a.brightness_score))
        .map((a) => ({ value: a.brightness_score, source: "selfie" })),
      ...registrations
        .filter((r) => isNumber(r.selfie_brightness_score))
        .map((r) => ({ value: r.selfie_brightness_score, source: "selfie" })),
      ...registrations
        .filter((r) => isNumber(r.id_card_brightness_score))
        .map((r) => ({ value: r.id_card_brightness_score, source: "id_card" })),
    ];
    return binByRange(entries, QUALITY_BIN_COUNT);
  }, [attempts, registrations]);

  // Excludes quality_rejected rows - those carry a zero-value confidence
  // sentinel because the model never ran, not a genuine low-confidence score.
  const confidenceData = useMemo(() => {
    const entries = [
      ...attempts
        .filter((a) => isNumber(a.confidence) && a.predicted_class !== "quality_rejected")
        .map((a) => ({ value: a.confidence, source: "liveness_check" })),
      ...registrations
        .filter((r) => isNumber(r.liveness_confidence) && r.liveness_predicted_class !== "quality_rejected")
        .map((r) => ({ value: r.liveness_confidence, source: "registration" })),
    ];
    return binFixedUnitRange(entries, SCORE_BIN_SIZE);
  }, [attempts, registrations]);

  const apiStats = useMemo(() => {
    const total = apiRequests.length;
    const errors = apiRequests.filter((r) => r.status_code >= 400).length;
    return {
      total,
      errors,
      successRate: total ? ((total - errors) / total) * 100 : 0,
      errorRate: total ? (errors / total) * 100 : 0,
    };
  }, [apiRequests]);

  const latencyOverTimeData = useMemo(() => {
    const byHour = new Map();
    for (const r of apiRequests) {
      const key = hourKey(r.created_at);
      const entry = byHour.get(key) || { key, durations: [] };
      entry.durations.push(r.duration_ms);
      byHour.set(key, entry);
    }
    return Array.from(byHour.values())
      .sort((a, b) => a.key.localeCompare(b.key))
      .map((entry) => {
        const sorted = [...entry.durations].sort((a, b) => a - b);
        return {
          hour: hourLabel(entry.key),
          avgMs: Math.round(average(sorted)),
          p95Ms: Math.round(percentile(sorted, 0.95)),
        };
      });
  }, [apiRequests]);

  const routeBreakdown = useMemo(() => {
    const byRoute = new Map();
    for (const r of apiRequests) {
      const entry = byRoute.get(r.route) || { route: r.route, count: 0, errors: 0, durations: [] };
      entry.count += 1;
      if (r.status_code >= 400) entry.errors += 1;
      entry.durations.push(r.duration_ms);
      byRoute.set(r.route, entry);
    }
    return Array.from(byRoute.values())
      .map((entry) => {
        const sorted = [...entry.durations].sort((a, b) => a - b);
        return {
          route: entry.route,
          count: entry.count,
          successRate: ((entry.count - entry.errors) / entry.count) * 100,
          errorRate: (entry.errors / entry.count) * 100,
          avgMs: average(sorted),
          p95Ms: percentile(sorted, 0.95),
        };
      })
      .sort((a, b) => b.count - a.count);
  }, [apiRequests]);

  return (
    <div className="stats-overview">
      <div className="stat-tiles">
        <StatTile
          label="Admin Override Rate (proxy — not FAR/FRR)"
          value={`${overrideStats.rate.toFixed(1)}%`}
          hint={`${overrideStats.overridden} of ${overrideStats.total} reviewed differ from the automated call`}
        />
        <StatTile
          label="API Success Rate"
          value={`${apiStats.successRate.toFixed(1)}%`}
          hint={`${apiStats.total - apiStats.errors} of ${apiStats.total} requests, last 24h`}
        />
        <StatTile
          label="API Error Rate"
          value={`${apiStats.errorRate.toFixed(1)}%`}
          hint={`${apiStats.errors} of ${apiStats.total} requests, last 24h`}
        />
      </div>

      <div className="chart-grid">
        <ChartCard
          title="Blur Score Distribution"
          empty={blurData.length === 0 ? "No quality scores logged yet." : null}
        >
          <BarChart data={blurData}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.border} />
            <XAxis dataKey="range" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={50} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="selfie" name="Selfie" stackId="a" fill={CHART_COLORS.primary} />
            <Bar dataKey="id_card" name="ID card" stackId="a" fill={CHART_COLORS.warning} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard
          title="Brightness Score Distribution"
          empty={brightnessData.length === 0 ? "No quality scores logged yet." : null}
        >
          <BarChart data={brightnessData}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.border} />
            <XAxis dataKey="range" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={50} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="selfie" name="Selfie" stackId="a" fill={CHART_COLORS.primary} />
            <Bar dataKey="id_card" name="ID card" stackId="a" fill={CHART_COLORS.warning} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard
          title="Liveness Confidence Distribution"
          empty={confidenceData.length === 0 ? "No liveness scores logged yet." : null}
        >
          <BarChart data={confidenceData}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.border} />
            <XAxis dataKey="range" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={50} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="liveness_check" name="Liveness check" stackId="a" fill={CHART_COLORS.primary} />
            <Bar dataKey="registration" name="Registration" stackId="a" fill={CHART_COLORS.warning} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard
          title="API Latency Over Time (avg / p95)"
          empty={latencyOverTimeData.length === 0 ? "No API requests logged yet." : null}
        >
          <LineChart data={latencyOverTimeData}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.border} />
            <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} unit="ms" />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="avgMs" name="Avg latency" stroke={CHART_COLORS.primary} strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="p95Ms" name="p95 latency" stroke={CHART_COLORS.danger} strokeWidth={2} dot={false} />
          </LineChart>
        </ChartCard>
      </div>

      <div className="attempts-table-wrapper">
        <table className="attempts-table">
          <thead>
            <tr>
              <th>Route</th>
              <th>Requests</th>
              <th>Success %</th>
              <th>Error %</th>
              <th>Avg Latency</th>
              <th>p95 Latency</th>
            </tr>
          </thead>
          <tbody>
            {routeBreakdown.length === 0 ? (
              <tr>
                <td colSpan={6} className="empty-state">
                  No API requests logged yet.
                </td>
              </tr>
            ) : (
              routeBreakdown.map((r) => (
                <tr key={r.route}>
                  <td>{r.route}</td>
                  <td>{r.count}</td>
                  <td>{r.successRate.toFixed(1)}%</td>
                  <td>{r.errorRate.toFixed(1)}%</td>
                  <td>{r.avgMs.toFixed(0)} ms</td>
                  <td>{r.p95Ms.toFixed(0)} ms</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
