import { useMemo } from "react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
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
import {
  CHART_COLORS,
  REGISTRATION_DECISION_COLORS,
} from "../utils/chartColors";

const REGISTRATION_DECISION_LABELS = {
  approved: "Approved",
  manual_review: "Manual review",
  rejected_face_mismatch: "Face mismatch",
  rejected_spoof: "Spoof",
  rejected_ktp_forgery: "KTP Forgery",
  rejected_manual: "Rejected (manual)",
  rejected_poor_quality: "Quality rejected",
};

const BIN_SIZE = 0.1;

function dayKey(isoString) {
  return isoString.slice(0, 10);
}

function countBy(items, keyFn) {
  const counts = new Map();
  for (const item of items) {
    const key = keyFn(item);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return counts;
}

function pctLabel({ percent }) {
  return `${(percent * 100).toFixed(0)}%`;
}

export default function StatsOverview({ registrations = [] }) {
  // 6 Multi-Pillar KPI Metrics for Mode 3 Complete Pipeline
  const pipelineStats = useMemo(() => {
    const total = registrations.length;
    const approvedCount = registrations.filter((r) => r.decision === "approved").length;
    const matchedCount = registrations.filter((r) => r.face_match_verified).length;
    const liveCount = registrations.filter((r) => r.liveness_predicted_class === "realperson").length;
    const ktpAuthenticCount = registrations.filter((r) => r.decision !== "rejected_ktp_forgery").length;
    const manualReviewCount = registrations.filter((r) => r.decision === "manual_review").length;

    return {
      total,
      approvedCount,
      approvalRate: total ? (approvedCount / total) * 100 : 0,
      matchedCount,
      matchRate: total ? (matchedCount / total) * 100 : 0,
      liveCount,
      livenessRate: total ? (liveCount / total) * 100 : 0,
      ktpAuthenticCount,
      ktpAuthenticRate: total ? (ktpAuthenticCount / total) * 100 : 0,
      manualReviewCount,
      manualReviewRate: total ? (manualReviewCount / total) * 100 : 0,
    };
  }, [registrations]);

  // Chart 1: Final Registration Decisions Breakdown
  const registrationDecisionData = useMemo(() => {
    const counts = countBy(registrations, (r) => r.decision);
    return Array.from(counts, ([id, value]) => ({
      id,
      name: REGISTRATION_DECISION_LABELS[id] || id,
      value,
    }));
  }, [registrations]);

  // Chart 2: Security Rejections Waterfall by Threat Vector
  const threatVectorData = useMemo(() => {
    const ktpSpoofs = registrations.filter((r) => r.decision === "rejected_ktp_forgery").length;
    const faceMismatches = registrations.filter((r) => r.decision === "rejected_face_mismatch").length;
    const selfieSpoofs = registrations.filter((r) => r.decision === "rejected_spoof").length;
    const manualReviews = registrations.filter((r) => r.decision === "manual_review").length;
    const qualityRejects = registrations.filter((r) => r.decision === "rejected_poor_quality").length;

    return [
      { name: "KTP Doc Spoof", count: ktpSpoofs, fill: REGISTRATION_DECISION_COLORS.rejected_ktp_forgery || "#e11d48" },
      { name: "Face Mismatch", count: faceMismatches, fill: REGISTRATION_DECISION_COLORS.rejected_face_mismatch || "#db2777" },
      { name: "Selfie Spoof", count: selfieSpoofs, fill: REGISTRATION_DECISION_COLORS.rejected_spoof || "#dc2626" },
      { name: "Manual Review / NIK", count: manualReviews, fill: REGISTRATION_DECISION_COLORS.manual_review || "#b45309" },
      { name: "Quality Rejected", count: qualityRejects, fill: CHART_COLORS.neutral },
    ].filter((d) => d.count > 0 || registrations.length === 0);
  }, [registrations]);

  // Chart 3: ArcFace Biometric Distance Distribution
  const faceMatchDistanceData = useMemo(() => {
    const withDistance = registrations.filter((r) => typeof r.face_match_distance === "number");
    if (withDistance.length === 0) return [];
    const maxDistance = Math.max(...withDistance.map((r) => r.face_match_distance));
    const binCount = Math.max(1, Math.ceil((maxDistance + 0.001) / BIN_SIZE));
    const bins = Array.from({ length: binCount }, (_, i) => ({
      range: `${(i * BIN_SIZE).toFixed(1)}-${((i + 1) * BIN_SIZE).toFixed(1)}`,
      matched: 0,
      notMatched: 0,
    }));
    for (const r of withDistance) {
      const idx = Math.min(binCount - 1, Math.floor(r.face_match_distance / BIN_SIZE));
      if (r.face_match_verified) bins[idx].matched += 1;
      else bins[idx].notMatched += 1;
    }
    return bins;
  }, [registrations]);

  // Chart 4: Selfie Liveness Model Confidence Distribution
  const livenessConfidenceData = useMemo(() => {
    const withConf = registrations.filter((r) => typeof r.liveness_confidence === "number");
    if (withConf.length === 0) return [];
    const binCount = 10;
    const bins = Array.from({ length: binCount }, (_, i) => ({
      range: `${(i * 0.1).toFixed(1)}-${((i + 1) * 0.1).toFixed(1)}`,
      real: 0,
      spoof: 0,
    }));
    for (const r of withConf) {
      const idx = Math.min(binCount - 1, Math.floor(r.liveness_confidence / 0.1));
      if (r.liveness_predicted_class === "realperson") {
        bins[idx].real += 1;
      } else {
        bins[idx].spoof += 1;
      }
    }
    return bins;
  }, [registrations]);

  // Chart 5: Onboarding Volume & Approvals Over Time
  const registrationsOverTimeData = useMemo(() => {
    const byDay = new Map();
    for (const r of registrations) {
      const day = dayKey(r.created_at);
      const entry = byDay.get(day) || { day, total: 0, approved: 0 };
      entry.total += 1;
      if (r.decision === "approved") entry.approved += 1;
      byDay.set(day, entry);
    }
    return Array.from(byDay.values()).sort((a, b) => a.day.localeCompare(b.day));
  }, [registrations]);

  // Chart 6: Document vs Selfie Quality Averages
  const qualityAverages = useMemo(() => {
    const idBlur = registrations.filter((r) => typeof r.id_card_blur_score === "number").map((r) => r.id_card_blur_score);
    const selfieBlur = registrations.filter((r) => typeof r.selfie_blur_score === "number").map((r) => r.selfie_blur_score);
    const idBright = registrations.filter((r) => typeof r.id_card_brightness_score === "number").map((r) => r.id_card_brightness_score);
    const selfieBright = registrations.filter((r) => typeof r.selfie_brightness_score === "number").map((r) => r.selfie_brightness_score);

    const avg = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);

    return [
      { metric: "Blur Variance", ktp: Math.round(avg(idBlur)), selfie: Math.round(avg(selfieBlur)) },
      { metric: "Brightness (0-255)", ktp: Math.round(avg(idBright)), selfie: Math.round(avg(selfieBright)) },
    ];
  }, [registrations]);

  return (
    <div className="stats-overview">
      <div className="overview-header-summary">
        <h2>Complete e-KYC Pipeline Performance</h2>
        <span className="overview-subtitle">
          Real-time analytics aggregating KTP Doc-PAD, deterministic NIK validation, ConvNeXt face liveness, and ArcFace biometric matching.
        </span>
      </div>

      <div className="stat-tiles stat-tiles-pipeline">
        <StatTile
          label="Total Onboardings"
          value={pipelineStats.total}
          hint="Complete pipeline runs"
        />
        <StatTile
          label="Pipeline Approval Rate"
          value={`${pipelineStats.approvalRate.toFixed(1)}%`}
          hint={`${pipelineStats.approvedCount} of ${pipelineStats.total} approved`}
        />
        <StatTile
          label="Biometric Match Rate"
          value={`${pipelineStats.matchRate.toFixed(1)}%`}
          hint={`${pipelineStats.matchedCount} of ${pipelineStats.total} verified`}
        />
        <StatTile
          label="Selfie Liveness Pass"
          value={`${pipelineStats.livenessRate.toFixed(1)}%`}
          hint={`${pipelineStats.liveCount} of ${pipelineStats.total} live`}
        />
        <StatTile
          label="KTP Authenticity Rate"
          value={`${pipelineStats.ktpAuthenticRate.toFixed(1)}%`}
          hint={`${pipelineStats.ktpAuthenticCount} of ${pipelineStats.total} authentic`}
        />
        <StatTile
          label="Manual Review Needed"
          value={`${pipelineStats.manualReviewRate.toFixed(1)}%`}
          hint={`${pipelineStats.manualReviewCount} of ${pipelineStats.total} flagged`}
        />
      </div>

      <div className="chart-grid">
        {/* Chart 1: Pipeline Decisions */}
        <ChartCard
          title="Pipeline Decisions Breakdown"
          empty={registrations.length === 0 ? "No registrations logged yet." : null}
        >
          <PieChart>
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Pie
              data={registrationDecisionData}
              dataKey="value"
              nameKey="name"
              innerRadius={55}
              outerRadius={85}
              paddingAngle={2}
              label={pctLabel}
            >
              {registrationDecisionData.map((entry) => (
                <Cell key={entry.id} fill={REGISTRATION_DECISION_COLORS[entry.id] || CHART_COLORS.primary} />
              ))}
            </Pie>
          </PieChart>
        </ChartCard>

        {/* Chart 2: Threat Vector Waterfall */}
        <ChartCard
          title="Security Rejections by Threat Vector"
          empty={threatVectorData.every((d) => d.count === 0) ? "No security rejections logged yet." : null}
        >
          <BarChart data={threatVectorData} layout="vertical" margin={{ left: 20, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.border} />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="count" name="Rejections" radius={[0, 4, 4, 0]}>
              {threatVectorData.map((entry, index) => (
                <Cell key={`threat-cell-${index}`} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ChartCard>

        {/* Chart 3: ArcFace Distance */}
        <ChartCard
          title="Face Match Distance Distribution (ArcFace)"
          empty={faceMatchDistanceData.length === 0 ? "No face-match distances recorded yet." : null}
        >
          <BarChart data={faceMatchDistanceData}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.border} />
            <XAxis dataKey="range" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={50} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="matched" name="Matched (<=0.68)" stackId="a" fill={CHART_COLORS.success} />
            <Bar dataKey="notMatched" name="Mismatch (>0.68)" stackId="a" fill={CHART_COLORS.danger} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        {/* Chart 4: Selfie Liveness Confidence */}
        <ChartCard
          title="Selfie Liveness Model Confidence"
          empty={livenessConfidenceData.length === 0 ? "No liveness confidence scores recorded yet." : null}
        >
          <BarChart data={livenessConfidenceData}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.border} />
            <XAxis dataKey="range" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={50} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="real" name="Real Person" stackId="a" fill={CHART_COLORS.success} />
            <Bar dataKey="spoof" name="Spoof Detected" stackId="a" fill={CHART_COLORS.danger} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        {/* Chart 5: Onboarding Volume Over Time */}
        <ChartCard
          title="Onboarding Volume & Approvals Over Time"
          empty={registrationsOverTimeData.length === 0 ? "No registrations logged yet." : null}
        >
          <LineChart data={registrationsOverTimeData}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.border} />
            <XAxis dataKey="day" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="total" name="Total Submissions" stroke={CHART_COLORS.primary} strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="approved" name="Approved" stroke={CHART_COLORS.success} strokeWidth={2} dot={false} />
          </LineChart>
        </ChartCard>

        {/* Chart 6: Document vs Selfie Quality Comparison */}
        <ChartCard
          title="KTP vs Selfie Quality Performance (Avg)"
          empty={registrations.length === 0 ? "No quality scores logged yet." : null}
        >
          <BarChart data={qualityAverages} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.border} />
            <XAxis dataKey="metric" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="ktp" name="Indonesian KTP" fill={CHART_COLORS.primary} radius={[4, 4, 0, 0]} />
            <Bar dataKey="selfie" name="Live Selfie" fill="#06b6d4" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>
      </div>
    </div>
  );
}
