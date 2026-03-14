const STAGE_ALIASES = {
  scanning: "scan",
  clustering: "compare",
  scoring: "compare",
};

export const SCAN_STAGE_META = {
  queued: {
    label: "ממתין",
    rangeStart: 0,
    rangeEnd: 0,
    strokeColor: "#8f8776",
    railColor: "rgba(143, 135, 118, 0.18)",
    chipColor: "#8f8776",
  },
  setup: {
    label: "מכין סריקה",
    rangeStart: 0,
    rangeEnd: 10,
    strokeColor: "#b98429",
    railColor: "rgba(185, 132, 41, 0.16)",
    chipColor: "#b98429",
  },
  scan: {
    label: "סורק תיקיות",
    rangeStart: 10,
    rangeEnd: 45,
    strokeColor: "#2f7a6d",
    railColor: "rgba(47, 122, 109, 0.16)",
    chipColor: "#2f7a6d",
  },
  matching: {
    label: "מאתר התאמות",
    rangeStart: 45,
    rangeEnd: 70,
    strokeColor: "#8a6489",
    railColor: "rgba(138, 100, 137, 0.16)",
    chipColor: "#8a6489",
  },
  quality: {
    label: "מחשב איכות",
    rangeStart: 70,
    rangeEnd: 84,
    strokeColor: "#3a73b8",
    railColor: "rgba(58, 115, 184, 0.16)",
    chipColor: "#3a73b8",
  },
  compare: {
    label: "משווה אלבומים",
    rangeStart: 84,
    rangeEnd: 99,
    strokeColor: "#b5662c",
    railColor: "rgba(181, 102, 44, 0.16)",
    chipColor: "#b5662c",
  },
  complete: {
    label: "הושלם",
    rangeStart: 100,
    rangeEnd: 100,
    strokeColor: "#4d8a57",
    railColor: "rgba(77, 138, 87, 0.16)",
    chipColor: "#4d8a57",
  },
};

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function toFiniteNumber(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

export function normalizeScanStage(stage) {
  if (!stage) return "queued";
  return STAGE_ALIASES[stage] ?? stage;
}

export function getScanStageMeta(stage) {
  const normalizedStage = normalizeScanStage(stage);
  return SCAN_STAGE_META[normalizedStage] ?? SCAN_STAGE_META.queued;
}

export function getStagePercent(progress = {}) {
  const total = toFiniteNumber(progress.total, 0);
  const current = toFiniteNumber(progress.current, 0);

  if (total > 0) {
    return Math.round(clamp((current / total) * 100, 0, 100));
  }

  return Math.round(clamp(toFiniteNumber(progress.percent, 0), 0, 100));
}

export function getOverallScanPercent(progress = {}) {
  const stageKey = normalizeScanStage(progress.stage ?? progress.step);
  if (stageKey === "complete") return 100;

  const stageMeta = getScanStageMeta(stageKey);
  const rawStageRatio = clamp(getStagePercent(progress) / 100, 0, 1);
  const weightedPercent = stageMeta.rangeStart + ((stageMeta.rangeEnd - stageMeta.rangeStart) * rawStageRatio);

  return Math.round(clamp(weightedPercent, 0, 100));
}

export function getScanProgressModel(progress = {}) {
  const stageKey = normalizeScanStage(progress.stage ?? progress.step);
  const stageMeta = getScanStageMeta(stageKey);

  return {
    stageKey,
    stageLabel: stageMeta.label,
    stagePercent: getStagePercent(progress),
    overallPercent: getOverallScanPercent(progress),
    strokeColor: stageMeta.strokeColor,
    railColor: stageMeta.railColor,
    chipColor: stageMeta.chipColor,
    isComplete: stageKey === "complete",
  };
}
