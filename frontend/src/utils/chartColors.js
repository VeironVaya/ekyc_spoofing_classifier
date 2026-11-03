// Mirrors the CSS custom properties in index.css - Recharts needs literal
// color strings (SVG fill/stroke), it can't read var() reliably here.
export const CHART_COLORS = {
  primary: "#7c3aed",
  primaryLight: "#ede9fe",
  success: "#15803d",
  warning: "#b45309",
  danger: "#dc2626",
  textMuted: "#6b6280",
  border: "#e4defa",
  neutral: "#9ca3af",
};

export const PREDICTED_CLASS_COLORS = {
  realperson: CHART_COLORS.success,
  fake_printed: CHART_COLORS.danger,
  fake_mask: "#ea580c",
  fake_mannequin: CHART_COLORS.warning,
  fake_screen: "#db2777",
  fake_unknown: CHART_COLORS.textMuted,
  quality_rejected: CHART_COLORS.neutral,
};

export const ATTEMPT_DECISION_COLORS = {
  continue_registration: CHART_COLORS.success,
  manual_review: CHART_COLORS.warning,
  blocked_flagged: CHART_COLORS.danger,
  rejected_poor_quality: CHART_COLORS.neutral,
};

export const REGISTRATION_DECISION_COLORS = {
  approved: CHART_COLORS.success,
  manual_review: CHART_COLORS.warning,
  rejected_face_mismatch: "#db2777",
  rejected_spoof: CHART_COLORS.danger,
  rejected_ktp_forgery: "#e11d48",
  rejected_manual: "#9f1239",
  rejected_poor_quality: CHART_COLORS.neutral,
};
