export function formatPercent(value) {
  if (value === null || value === undefined) return "ללא נתון";
  return `${Number(value).toFixed(1)}%`;
}
export function formatRatio(value) {
  if (value === null || value === undefined) return "ללא נתון";
  return `${Math.round(Number(value) * 100)}%`;
}
export function formatDuration(value) {
  if (!value) return "ללא נתון";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${seconds}`;
}
export function formatBitrate(value) {
  if (value === null || value === undefined) return "ללא נתון";
  return `${Math.round(Number(value))} kbps`;
}
export function formatSizeMb(value) {
  if (value === null || value === undefined) return "0 MB";
  if (value >= 1024) return `${(value / 1024).toFixed(2)} GB`;
  return `${Number(value).toFixed(1)} MB`;
}
export const METRICS = [
  { key: "quality_score", label: "איכות כללית", type: "percent" },
  { key: "avg_bitrate", label: "קצב נתונים ממוצע", type: "bitrate" },
  { key: "file_count", label: "מספר קבצים", type: "count" },
  { key: "total_size_mb", label: "גודל כולל", type: "size" },
  { key: "lossless_ratio", label: "קבצים באיכות מקור", type: "ratio" },
  { key: "lyrics_ratio", label: "קבצים עם מילים", type: "ratio" },
];
export function formatMetricValue(type, value) {
  if (type === "percent") return formatPercent(value);
  if (type === "ratio") return formatRatio(value);
  if (type === "bitrate") return formatBitrate(value);
  if (type === "size") return formatSizeMb(value);
  if (type === "duration") return formatDuration(value);
  if (type === "count") {
    if (value === null || value === undefined) return "ללא נתון";
    return String(value);
  }
  if (value === null || value === undefined) return "ללא נתון";
  return String(value);
}
export function hasClusterDecision(decisions, clusterId) {
  return Object.prototype.hasOwnProperty.call(decisions, clusterId);
}
export function getActiveKeeperId(cluster, decisions = {}) {
  if (!cluster) return null;
  if (hasClusterDecision(decisions, cluster.cluster_id)) {
    return decisions[cluster.cluster_id] ?? null;
  }
  return cluster.recommended_keeper_id ?? null;
}
export function getClusterDisplayTitle(cluster) {
  if (!cluster?.albums?.length) return "קבוצת השוואה";
  const names = Array.from(
    new Set(
      cluster.albums
        .filter((album) => !album.is_deleted)
        .map((album) => album.name?.trim())
        .filter(Boolean),
    ),
  );
  if (!names.length) return "קבוצת השוואה";
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} מול ${names[1]}`;
  return `${names[0]} מול ${names[1]} ועוד ${names.length - 2}`;
}
export function getMetricWinners(albums) {
  const winners = {};
  METRICS.forEach((metric) => {
    const candidates = albums
      .filter((album) => !album.is_deleted && album[metric.key] !== null && album[metric.key] !== undefined)
      .map((album) => ({ albumId: album.folder_id, value: album[metric.key] }));
    if (!candidates.length) {
      winners[metric.key] = null;
      return;
    }
    const values = candidates.map((candidate) => candidate.value);
    const max = Math.max(...values);
    const min = Math.min(...values);
    winners[metric.key] = max === min ? null : candidates.find((candidate) => candidate.value === max)?.albumId ?? null;
  });
  return winners;
}
export function buildTrackComparisonRows(albums) {
  const rows = new Map();
  albums.forEach((album) => {
    album.tracks.forEach((track) => {
      const key = [track.title || track.filename, track.artist || "", Math.round(track.duration || 0)].join("|");
      if (!rows.has(key)) {
        rows.set(key, {
          key,
          title: track.title || track.filename,
          artist: track.artist || "ללא אמן",
          duration: track.duration,
          entries: {},
        });
      }
      rows.get(key).entries[album.folder_id] = {
        filename: track.filename,
        title: track.title || track.filename,
        artist: track.artist || "ללא אמן",
        duration: track.duration,
        size_mb: track.size_mb,
        bitrate: track.bitrate,
      };
    });
  });
  return Array.from(rows.values()).sort((a, b) => a.title.localeCompare(b.title, "he"));
}

export function getPairNarratives(pairs, albums) {
  const albumNames = Object.fromEntries(albums.map((album) => [album.folder_id, album.name]));
  return pairs.map((pair) => {
    const finalScore = Number(pair.final_score ?? pair.base_score ?? 0);
    const isSafe = finalScore >= 97 || pair.is_identical_by_hash;
    const scoreLabel = pair.is_identical_by_hash ? "זהים לחלוטין" : `${finalScore.toFixed(1)}% דמיון`;
    let description = "זוהו קווי דמיון משמעותיים בין שני העותקים.";
    if (pair.is_identical_by_hash) {
      description = "הקבצים והמבנה תואמים לחלוטין, ולכן אפשר להתייחס אליהם כאל עותקים זהים.";
    } else if (pair.gemini_reason) {
      description = pair.gemini_reason;
    } else if (pair.reason_codes?.includes("safe_threshold")) {
      description = "הציון הסופי עבר את סף המחיקה הבטוחה, כך שהמערכת בטוחה יחסית בהמלצה.";
    } else if (pair.reason_codes?.includes("review_threshold")) {
      description = "העותקים דומים מאוד, אבל נדרש אישור משתמש לפני מחיקה כי הזיהוי עדיין גבולי.";
    }
    return {
      id: pair.pair_id,
      title: `${albumNames[pair.folder1_id] ?? "עותק A"} מול ${albumNames[pair.folder2_id] ?? "עותק B"}`,
      description,
      scoreLabel,
      tone: isSafe ? "success" : "warning",
    };
  });
}
