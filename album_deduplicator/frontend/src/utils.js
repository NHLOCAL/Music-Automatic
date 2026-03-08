export function formatPercent(value) {
  if (value === null || value === undefined) return "ללא נתון";
  return `${Number(value).toFixed(1)}/100`;
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
  { key: "quality_score", label: "דירוג איכות מומלץ", type: "percent" },
  { key: "avg_bitrate", label: "איכות שמע (Bitrate)", type: "bitrate" },
  { key: "file_count", label: "כמות קבצים", type: "count" },
  { key: "total_size_mb", label: "גודל התיקייה", type: "size" },
  { key: "lossless_ratio", label: "קובצי אודיו ללא כיווץ", type: "ratio" },
  { key: "lyrics_ratio", label: "מילים מובנות לשירים", type: "ratio" },
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
  if (names.length === 2) return `${names[0]} vs ${names[1]}`;
  return `${names[0]} ועוד ${names.length - 1} עותקים`;
}

export function getClusterListSubtitle(cluster) {
  const albumCount = cluster?.albums?.filter((album) => !album.is_deleted).length ?? 0;
  return `${albumCount} עותקים להשוואה`;
}

export function getAlbumOrdinalLabel(index) {
  return `עותק ${index + 1}`;
}

export function getClusterStatusMeta(cluster, hasDecision) {
  if (!cluster) {
    return { label: "ממתין לסקירה", tone: "neutral" };
  }
  if (cluster.confidence_bucket === "safe") {
    return cluster.resolution_state === "auto" || hasDecision
      ? { label: "בטוח למחיקה", tone: "success" }
      : { label: "דורש אישור מחיקה", tone: "warning" };
  }
  if (hasDecision) {
    return { label: "נבדק ומוכן", tone: "success" };
  }
  return { label: "ממתין לסקירה", tone: "neutral" };
}

export function getClusterSortPriority(cluster, decisions = {}) {
  if (!cluster) return 99;
  const hasDecision = hasClusterDecision(decisions, cluster.cluster_id) && decisions[cluster.cluster_id] !== null;
  const statusMeta = getClusterStatusMeta(cluster, hasDecision);
  if (statusMeta.label === "נבדק ומוכן") return 0;
  return 1;
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
    const tracks = Array.isArray(album.tracks) ? album.tracks : [];
    tracks.forEach((track) => {
      const key = [track.title || track.filename, track.artist || "", Math.round(track.duration || 0)].join("|");
      if (!rows.has(key)) {
        rows.set(key, {
          key,
          title: track.title || track.filename,
          artist: track.artist || "אמן לא ידוע",
          duration: track.duration,
          entries: {},
        });
      }
      rows.get(key).entries[album.folder_id] = {
        filename: track.filename,
        title: track.title || track.filename,
        artist: track.artist || "אמן לא ידוע",
        duration: track.duration,
        size_mb: track.size_mb,
        bitrate: track.bitrate,
      };
    });
  });
  return Array.from(rows.values()).sort((a, b) => a.title.localeCompare(b.title, "he"));
}

function normalizeTrackValue(field, value) {
  if (value === null || value === undefined || value === "") return null;
  if (field === "duration") return Math.round(Number(value));
  if (field === "size_mb") return Number(value).toFixed(2);
  if (field === "bitrate") return Math.round(Number(value));
  return String(value).trim().toLocaleLowerCase("he");
}

export function getTrackFieldTone(row, albumIds, field) {
  const values = albumIds
    .map((albumId) => row.entries[albumId])
    .filter(Boolean)
    .map((entry) => normalizeTrackValue(field, entry[field]))
    .filter((value) => value !== null);
  if (values.length <= 1) return "same";
  return new Set(values).size === 1 ? "same" : "different";
}

export function getTrackRowTone(row, albumIds) {
  const comparableFields = ["title", "filename", "duration", "size_mb", "bitrate"];
  return comparableFields.some((field) => getTrackFieldTone(row, albumIds, field) === "different")
    ? "different"
    : "same";
}
