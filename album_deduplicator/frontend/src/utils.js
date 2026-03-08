export function formatPercent(value) {
  if (value === null || value === undefined) return "N/A";
  return `${Number(value).toFixed(1)}%`;
}
export function formatRatio(value) {
  if (value === null || value === undefined) return "N/A";
  return `${Math.round(Number(value) * 100)}%`;
}
export function formatDuration(value) {
  if (!value) return "N/A";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${seconds}`;
}
export function formatBitrate(value) {
  if (value === null || value === undefined) return "N/A";
  return `${Math.round(Number(value))} kbps`;
}
export function formatSizeMb(value) {
  if (value === null || value === undefined) return "0 MB";
  if (value >= 1024) return `${(value / 1024).toFixed(2)} GB`;
  return `${Number(value).toFixed(1)} MB`;
}
export const METRICS = [
  { key: "quality_score", label: "איכות משוקללת", type: "percent" },
  { key: "avg_bitrate", label: "ביטרייט", type: "bitrate" },
  { key: "file_count", label: "מספר קבצים", type: "count" },
  { key: "total_size_mb", label: "נפח כולל", type: "size" },
  { key: "lossless_ratio", label: "פורמט Lossless", type: "ratio" },
  { key: "lyrics_ratio", label: "מכיל מילים", type: "ratio" },
];
export function formatMetricValue(type, value) {
  if (type === "percent") return formatPercent(value);
  if (type === "ratio") return formatRatio(value);
  if (type === "bitrate") return formatBitrate(value);
  if (type === "size") return formatSizeMb(value);
  if (value === null || value === undefined) return "N/A";
  return String(value);
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
          presence: {},
        });
      }
      rows.get(key).presence[album.folder_id] = true;
    });
  });
  return Array.from(rows.values()).sort((a, b) => a.title.localeCompare(b.title, "he"));
}