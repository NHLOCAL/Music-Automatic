import { useEffect, useMemo, useState, startTransition } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const TABS = [
  { id: "safe", label: "בטוח למחיקה" },
  { id: "review", label: "דורש סקירה" },
  { id: "all", label: "כל התוצאות" },
];
const METRICS = [
  { key: "quality_score", label: "איכות", type: "percent" },
  { key: "avg_bitrate", label: "ביטרייט", type: "bitrate" },
  { key: "file_count", label: "שירים", type: "count" },
  { key: "total_size_mb", label: "נפח", type: "size" },
  { key: "lossless_ratio", label: "Lossless", type: "ratio" },
  { key: "lyrics_ratio", label: "מילים", type: "ratio" },
];

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

function formatPercent(value) {
  if (value === null || value === undefined) return "N/A";
  return `${Number(value).toFixed(1)}%`;
}

function formatRatio(value) {
  if (value === null || value === undefined) return "N/A";
  return `${Math.round(Number(value) * 100)}%`;
}

function formatDuration(value) {
  if (!value) return "N/A";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function formatBitrate(value) {
  if (value === null || value === undefined) return "N/A";
  return `${Math.round(Number(value))} kbps`;
}

function formatSizeMb(value) {
  if (value === null || value === undefined) return "0 MB";
  if (value >= 1024) return `${(value / 1024).toFixed(2)} GB`;
  return `${Number(value).toFixed(1)} MB`;
}

function formatMetricValue(type, value) {
  if (type === "percent") return formatPercent(value);
  if (type === "ratio") return formatRatio(value);
  if (type === "bitrate") return formatBitrate(value);
  if (type === "size") return formatSizeMb(value);
  if (value === null || value === undefined) return "N/A";
  return String(value);
}

function bucketLabel(bucket) {
  return bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה";
}

function resolutionLabel(state) {
  if (state === "auto") return "אוטומטי";
  if (state === "user_selected") return "בחירה ידנית";
  if (state === "deleted") return "טופל";
  return "דלוג";
}

function toneLabel(tone) {
  if (tone === "positive") return "יתרון";
  if (tone === "warning") return "דורש תשומת לב";
  if (tone === "negative") return "חיסרון";
  return "מידע";
}

function hydrateDecisions(clusters, previous) {
  const next = { ...previous };
  clusters.forEach((cluster) => {
    if (!(cluster.cluster_id in next)) {
      next[cluster.cluster_id] = cluster.resolution_state === "auto" ? cluster.recommended_keeper_id : null;
    }
  });
  return next;
}

function getCurrentKeeperId(cluster, decisions) {
  const current = decisions[cluster.cluster_id];
  if (current !== undefined) return current;
  return cluster.resolution_state === "auto" ? cluster.recommended_keeper_id : null;
}

function getNextAlbumId(cluster, currentAlbumId, direction) {
  const visibleAlbums = cluster.albums.filter((album) => !album.is_deleted);
  if (!visibleAlbums.length) return null;
  const index = visibleAlbums.findIndex((album) => album.folder_id === currentAlbumId);
  if (index === -1) return visibleAlbums[0].folder_id;
  const offset = direction === "next" ? 1 : -1;
  return visibleAlbums[(index + offset + visibleAlbums.length) % visibleAlbums.length].folder_id;
}

function getDeleteCandidate(cluster, keeperId) {
  return cluster.albums.find((album) => !album.is_deleted && album.folder_id !== keeperId) ?? null;
}

function buildTrackComparisonRows(albums) {
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

function getMetricWinners(albums) {
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

function ClusterCard({ cluster, isActive, currentKeeperId, onSelect, onChooseKeeper }) {
  return (
    <article className={isActive ? "clusterCard clusterCard--active" : "clusterCard"} onClick={() => onSelect(cluster.cluster_id)}>
      <div className="clusterCard__header">
        <div className="clusterCard__labels">
          <span className={`bucketBadge bucketBadge--${cluster.confidence_bucket}`}>{bucketLabel(cluster.confidence_bucket)}</span>
          <span className={`resolutionBadge resolutionBadge--${cluster.resolution_state}`}>{resolutionLabel(cluster.resolution_state)}</span>
        </div>
        <div className="clusterMiniScores">
          {cluster.comparison_highlights.slice(0, 2).map((highlight) => (
            <span key={highlight.id} className={`miniHighlight miniHighlight--${highlight.tone}`}>
              {highlight.label}
            </span>
          ))}
        </div>
      </div>
      <h3>{cluster.albums.map((album) => album.name).join(" / ")}</h3>
      <p className="clusterSummary">{cluster.human_summary}</p>
      <div className="keeperLine">
        <strong>שמור:</strong>
        <span>{currentKeeperId ? cluster.albums.find((album) => album.folder_id === currentKeeperId)?.name : "דלג כרגע"}</span>
      </div>
      <div className="choiceStrip">
        {cluster.albums
          .filter((album) => !album.is_deleted)
          .map((album) => (
            <button
              key={album.folder_id}
              type="button"
              className={currentKeeperId === album.folder_id ? "albumChoice albumChoice--selected" : "albumChoice"}
              onClick={(event) => {
                event.stopPropagation();
                onChooseKeeper(cluster.cluster_id, album.folder_id);
              }}
            >
              <span>{album.name}</span>
              <strong>{formatPercent(album.quality_score)}</strong>
            </button>
          ))}
        <button
          type="button"
          className={!currentKeeperId ? "albumChoice albumChoice--selected" : "albumChoice"}
          onClick={(event) => {
            event.stopPropagation();
            onChooseKeeper(cluster.cluster_id, null);
          }}
        >
          דלג
        </button>
      </div>
    </article>
  );
}

function AlbumComparisonCard({
  album,
  isKeeper,
  isFocused,
  metricWinners,
  highlights,
  onChooseKeeper,
  onOpenExplorer,
  onDeleteNow,
  onFocus,
}) {
  return (
    <section
      className={["albumPanel", isKeeper ? "albumPanel--keeper" : "", isFocused ? "albumPanel--focused" : "", album.is_deleted ? "albumPanel--deleted" : ""].filter(Boolean).join(" ")}
      onClick={() => onFocus(album.folder_id)}
    >
      <header className="albumPanel__header">
        <div>
          <div className="albumPanel__titleRow">
            <h4>{album.name}</h4>
            {isKeeper ? <span className="keeperBadge">עותק נשמר</span> : null}
            {album.is_deleted ? <span className="deletedBadge">כבר הועבר לסל</span> : null}
          </div>
          <p className="albumPath">{album.path}</p>
        </div>
        <div className="albumPanel__actions">
          {!album.is_deleted ? <button className="ghostButton ghostButton--small" type="button" onClick={() => onOpenExplorer(album.path)}>פתח באקספלורר</button> : null}
          {!album.is_deleted && !isKeeper ? <button className="ghostButton ghostButton--small" type="button" onClick={() => onChooseKeeper(album.folder_id)}>בחר כעותק נשמר</button> : null}
          {!album.is_deleted && !isKeeper ? <button className="dangerGhostButton" type="button" onClick={() => onDeleteNow(album)}>מחק עכשיו</button> : null}
        </div>
      </header>
      <div className="albumHighlights">
        {highlights.length ? highlights.map((highlight) => (
          <span key={highlight.id} className={`highlightPill highlightPill--${highlight.tone}`}>
            <strong>{toneLabel(highlight.tone)}</strong>
            {highlight.label}
            {highlight.value ? ` · ${highlight.value}` : ""}
          </span>
        )) : <span className="subtleText">אין הבדל בולט ביחס לשאר האלבומים בקבוצה.</span>}
      </div>
      <div className="metricGrid">
        {METRICS.map((metric) => (
          <div key={metric.key} className={metricWinners[metric.key] === album.folder_id ? "metricCard metricCard--winner" : "metricCard"}>
            <span>{metric.label}</span>
            <strong>{formatMetricValue(metric.type, album[metric.key])}</strong>
          </div>
        ))}
        <div className={album.has_album_art ? "metricCard metricCard--winner" : "metricCard metricCard--warning"}>
          <span>עטיפה</span>
          <strong>{album.has_album_art ? "קיימת" : "חסרה"}</strong>
        </div>
        <div className={album.in_preferred_root ? "metricCard metricCard--winner" : "metricCard"}>
          <span>מיקום מועדף</span>
          <strong>{album.in_preferred_root ? "כן" : "לא"}</strong>
        </div>
      </div>
    </section>
  );
}

function ShortcutOverlay({ onClose }) {
  const rows = [
    ["↑ / ↓", "מעבר בין קבוצות"],
    ["← / →", "בחירת keeper אחר"],
    ["Space", "דלג על הקבוצה"],
    ["Enter", "פתח אישור למחיקה מרוכזת"],
    ["O", "פתח את האלבום המסומן באקספלורר"],
    ["D", "פתח אישור למחיקה בודדת"],
    ["?", "פתח או סגור את רשימת הקיצורים"],
  ];
  return (
    <div className="overlay" role="dialog" aria-modal="true">
      <div className="modal modal--shortcuts">
        <div className="modal__header">
          <div>
            <div className="sectionEyebrow">Keyboard Power Mode</div>
            <h3>קיצורי מקלדת</h3>
          </div>
          <button className="ghostButton ghostButton--small" type="button" onClick={onClose}>סגור</button>
        </div>
        <div className="shortcutList">
          {rows.map(([shortcut, description]) => (
            <div key={shortcut} className="shortcutRow">
              <kbd>{shortcut}</kbd>
              <span>{description}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ConfirmDialog({ title, body, confirmText, onConfirm, onCancel, tone = "default" }) {
  return (
    <div className="overlay" role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modal__header">
          <div>
            <div className="sectionEyebrow">אישור פעולה</div>
            <h3>{title}</h3>
          </div>
        </div>
        <p className="modal__body">{body}</p>
        <div className="modal__actions">
          <button className={tone === "danger" ? "dangerButton" : "primaryButton"} type="button" onClick={onConfirm}>{confirmText}</button>
          <button className="ghostButton" type="button" onClick={onCancel}>חזור לסקירה</button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [form, setForm] = useState({
    folders: "",
    preferred_root: "",
    force_rescan: false,
    clear_cache: false,
    bitrate_mode: "128",
    gemini_enabled: false,
  });
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState({
    step: "queued",
    stage: "queued",
    message: "ממתין",
    human_message: "ממתין לתחילת הניתוח.",
    current: 0,
    total: 1,
    percent: 0,
    warnings: [],
  });
  const [summary, setSummary] = useState(null);
  const [selectedTab, setSelectedTab] = useState("safe");
  const [clusters, setClusters] = useState([]);
  const [decisions, setDecisions] = useState({});
  const [preview, setPreview] = useState({
    items: [],
    total_count: 0,
    total_size_mb: 0,
    auto_selected_count: 0,
    manual_selected_count: 0,
  });
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  const [focusedAlbumId, setFocusedAlbumId] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [executingDelete, setExecutingDelete] = useState(false);
  const [singleDeleteTarget, setSingleDeleteTarget] = useState(null);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  const [successSummary, setSuccessSummary] = useState(null);

  useEffect(() => {
    if (!sessionId) return undefined;
    const events = new EventSource(`${API_BASE}/api/analysis-sessions/${sessionId}/events`);

    events.addEventListener("progress", (event) => {
      const data = JSON.parse(event.data);
      setProgress(data);
      setStatus("running");
    });

    events.addEventListener("completed", async () => {
      setStatus("completed");
      await refreshSession(sessionId);
      await refreshClusters(sessionId, selectedTab);
      await refreshPreview(sessionId);
    });

    events.addEventListener("failed", (event) => {
      const data = JSON.parse(event.data);
      setStatus("failed");
      setError(data.error ?? "הניתוח נכשל.");
    });

    events.addEventListener("delete_execution", async (event) => {
      const data = JSON.parse(event.data);
      setSuccessSummary({
        moved_count: data.moved_count,
        total_size_mb: data.total_size_mb ?? 0,
      });
      await refreshClusters(sessionId, selectedTab);
      await refreshPreview(sessionId);
    });

    events.addEventListener("end", () => {
      events.close();
    });

    return () => events.close();
  }, [selectedTab, sessionId]);

  useEffect(() => {
    if (!sessionId || status !== "completed") return;
    refreshClusters(sessionId, selectedTab);
  }, [selectedTab, sessionId, status]);

  const selectedCluster = useMemo(
    () => clusters.find((cluster) => cluster.cluster_id === selectedClusterId) ?? null,
    [clusters, selectedClusterId],
  );
  const currentKeeperId = useMemo(
    () => (selectedCluster ? getCurrentKeeperId(selectedCluster, decisions) : null),
    [decisions, selectedCluster],
  );
  const metricWinners = useMemo(
    () => (selectedCluster ? getMetricWinners(selectedCluster.albums) : {}),
    [selectedCluster],
  );
  const trackComparisonRows = useMemo(
    () => (selectedCluster ? buildTrackComparisonRows(selectedCluster.albums.filter((album) => !album.is_deleted)) : []),
    [selectedCluster],
  );
  const selectedAlbumHighlights = useMemo(() => {
    if (!selectedCluster) return {};
    return selectedCluster.comparison_highlights.reduce((accumulator, highlight) => {
      if (!highlight.album_id) return accumulator;
      accumulator[highlight.album_id] = [...(accumulator[highlight.album_id] ?? []), highlight];
      return accumulator;
    }, {});
  }, [selectedCluster]);

  useEffect(() => {
    if (!selectedCluster) {
      setFocusedAlbumId(null);
      return;
    }
    const visibleAlbums = selectedCluster.albums.filter((album) => !album.is_deleted);
    if (!visibleAlbums.some((album) => album.folder_id === focusedAlbumId)) {
      setFocusedAlbumId(currentKeeperId ?? visibleAlbums[0]?.folder_id ?? null);
    }
  }, [currentKeeperId, focusedAlbumId, selectedCluster]);

  useEffect(() => {
    const onKeyDown = (event) => {
      const targetTag = event.target?.tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(targetTag)) return;

      if (event.key === "?") {
        event.preventDefault();
        setShowShortcuts((current) => !current);
        return;
      }
      if (event.key === "Escape") {
        setShowShortcuts(false);
        setBulkConfirmOpen(false);
        setSingleDeleteTarget(null);
        return;
      }
      if (status !== "completed" || !selectedCluster) return;

      const clusterIndex = clusters.findIndex((cluster) => cluster.cluster_id === selectedCluster.cluster_id);
      if (event.key === "ArrowDown" && clusterIndex < clusters.length - 1) {
        event.preventDefault();
        setSelectedClusterId(clusters[clusterIndex + 1].cluster_id);
        return;
      }
      if (event.key === "ArrowUp" && clusterIndex > 0) {
        event.preventDefault();
        setSelectedClusterId(clusters[clusterIndex - 1].cluster_id);
        return;
      }
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const nextAlbumId = getNextAlbumId(
          selectedCluster,
          currentKeeperId ?? focusedAlbumId,
          event.key === "ArrowLeft" ? "previous" : "next",
        );
        if (nextAlbumId) {
          setFocusedAlbumId(nextAlbumId);
          updateDecision(selectedCluster.cluster_id, nextAlbumId);
        }
        return;
      }
      if (event.key === " ") {
        event.preventDefault();
        updateDecision(selectedCluster.cluster_id, null);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        if (singleDeleteTarget) {
          executeSingleDelete(singleDeleteTarget);
        } else if (preview.total_count > 0) {
          setBulkConfirmOpen(true);
        }
        return;
      }
      if (event.key.toLowerCase() === "o") {
        event.preventDefault();
        const album =
          selectedCluster.albums.find((candidate) => candidate.folder_id === (focusedAlbumId ?? currentKeeperId)) ??
          selectedCluster.albums.find((candidate) => !candidate.is_deleted);
        if (album) openExplorer(album.path);
        return;
      }
      if (event.key.toLowerCase() === "d") {
        event.preventDefault();
        const candidate = getDeleteCandidate(selectedCluster, currentKeeperId);
        if (candidate) {
          setSingleDeleteTarget({
            clusterId: selectedCluster.cluster_id,
            folderId: candidate.folder_id,
            name: candidate.name,
          });
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [clusters, currentKeeperId, focusedAlbumId, preview.total_count, selectedCluster, singleDeleteTarget, status]);

  async function refreshSession(currentSessionId) {
    const data = await requestJson(`/api/analysis-sessions/${currentSessionId}`);
    setSummary(data);
    setProgress(data.progress);
  }

  async function refreshClusters(currentSessionId, bucket) {
    const data = await requestJson(`/api/analysis-sessions/${currentSessionId}/clusters?bucket=${bucket}`);
    startTransition(() => {
      setClusters(data.clusters);
      setSelectedClusterId((previous) =>
        data.clusters.some((cluster) => cluster.cluster_id === previous) ? previous : data.clusters[0]?.cluster_id ?? null,
      );
      setDecisions((previous) => hydrateDecisions(data.clusters, previous));
    });
  }

  async function refreshPreview(currentSessionId) {
    const data = await requestJson(`/api/analysis-sessions/${currentSessionId}/delete-preview`);
    setPreview(data);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setActionMessage("");
    setSuccessSummary(null);
    try {
      const payload = {
        ...form,
        folders: form.folders
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        preferred_root: form.preferred_root || null,
      };
      const created = await requestJson("/api/analysis-sessions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setSessionId(created.session_id);
      setStatus(created.status);
      setClusters([]);
      setDecisions({});
      setPreview({
        items: [],
        total_count: 0,
        total_size_mb: 0,
        auto_selected_count: 0,
        manual_selected_count: 0,
      });
      setSelectedClusterId(null);
      await refreshSession(created.session_id);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setLoading(false);
    }
  }

  async function updateDecision(clusterId, keeperId) {
    if (!sessionId) return;
    const nextDecisions = { ...decisions, [clusterId]: keeperId };
    setDecisions(nextDecisions);
    try {
      const payload = {
        decisions: Object.entries(nextDecisions).map(([currentClusterId, currentKeeperId]) => ({
          cluster_id: currentClusterId,
          keeper_id: currentKeeperId,
        })),
      };
      const nextPreview = await requestJson(`/api/analysis-sessions/${sessionId}/decisions`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setPreview(nextPreview);
      await refreshClusters(sessionId, selectedTab);
    } catch (decisionError) {
      setError(decisionError.message);
    }
  }

  async function openExplorer(path) {
    try {
      await requestJson("/api/system/open-explorer", {
        method: "POST",
        body: JSON.stringify({ path }),
      });
      setActionMessage("האלבום נפתח באקספלורר.");
    } catch (openError) {
      setError(openError.message);
    }
  }

  async function executeSingleDelete(target) {
    if (!sessionId || !target) return;
    setSingleDeleteTarget(null);
    setError("");
    try {
      const execution = await requestJson(`/api/analysis-sessions/${sessionId}/delete-single`, {
        method: "POST",
        body: JSON.stringify({
          cluster_id: target.clusterId,
          folder_id: target.folderId,
        }),
      });
      await refreshSession(sessionId);
      await refreshClusters(sessionId, selectedTab);
      await refreshPreview(sessionId);
      setSuccessSummary({
        moved_count: execution.moved_count,
        total_size_mb: execution.total_size_mb ?? 0,
      });
      setActionMessage(`"${target.name}" הועבר לסל המחזור.`);
    } catch (executionError) {
      setError(executionError.message);
    }
  }

  async function executeDelete() {
    if (!sessionId || preview.total_count === 0) return;
    setExecutingDelete(true);
    setError("");
    try {
      const execution = await requestJson(`/api/analysis-sessions/${sessionId}/delete-executions`, {
        method: "POST",
        body: JSON.stringify({ folder_ids: preview.items.map((item) => item.folder_id) }),
      });
      await refreshSession(sessionId);
      await refreshClusters(sessionId, selectedTab);
      await refreshPreview(sessionId);
      setSuccessSummary({
        moved_count: execution.moved_count,
        total_size_mb: execution.total_size_mb ?? 0,
      });
      setBulkConfirmOpen(false);
      setActionMessage(`הועברו ${execution.moved_count} תיקיות לסל המחזור.`);
    } catch (executionError) {
      setError(executionError.message);
    } finally {
      setExecutingDelete(false);
    }
  }

  return (
    <div className="shell" dir="rtl">
      <aside className="hero">
        <div className="hero__eyebrow">Music Automatic / Album Deduplicator</div>
        <h1>סקירת כפילויות שמרגישה בטוחה, ברורה ומהירה</h1>
        <p className="hero__lead">
          המערכת מסבירה מה היא רואה בשפה אנושית, מדגישה רק את ההבדלים החשובים, ומעבירה למחיקה רק מה שבאמת
          בטוח.
        </p>

        <form className="panel panel--glass" onSubmit={handleSubmit}>
          <label className="field">
            <span>תיקיות קלט</span>
            <textarea
              rows={5}
              placeholder={"C:\\Music\nD:\\Archive"}
              value={form.folders}
              onChange={(event) => setForm((current) => ({ ...current, folders: event.target.value }))}
            />
          </label>

          <label className="field">
            <span>תיקייה מועדפת לשמירה</span>
            <input
              type="text"
              placeholder="אופציונלי, מתוך אחת מתיקיות הקלט"
              value={form.preferred_root}
              onChange={(event) => setForm((current) => ({ ...current, preferred_root: event.target.value }))}
            />
          </label>

          <div className="actionRow">
            <button className="primaryButton" type="submit" disabled={loading}>
              {loading ? "מתחיל ניתוח..." : "התחל ניתוח"}
            </button>
            <button className="ghostButton" type="button" onClick={() => setAdvancedOpen((current) => !current)}>
              {advancedOpen ? "סגור אפשרויות מתקדמות" : "פתח אפשרויות מתקדמות"}
            </button>
          </div>

          {advancedOpen ? (
            <div className="advancedGrid">
              <label className="field field--compact">
                <span>יעד ביטרייט לאיכות</span>
                <select
                  value={form.bitrate_mode}
                  onChange={(event) => setForm((current) => ({ ...current, bitrate_mode: event.target.value }))}
                >
                  <option value="128">128</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={form.force_rescan}
                  onChange={(event) => setForm((current) => ({ ...current, force_rescan: event.target.checked }))}
                />
                <span>אלץ סריקה מחדש</span>
              </label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={form.clear_cache}
                  onChange={(event) => setForm((current) => ({ ...current, clear_cache: event.target.checked }))}
                />
                <span>נקה cache של השוואות</span>
              </label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={form.gemini_enabled}
                  onChange={(event) => setForm((current) => ({ ...current, gemini_enabled: event.target.checked }))}
                />
                <span>Gemini לזוגות גבוליים בלבד</span>
              </label>
            </div>
          ) : null}

          <div className="mlBadge">
            <strong>ML פעיל כברירת מחדל.</strong>
            <span>כש-Gemini אינו זמין, התוצאות עדיין מוצגות והמערכת נשארת שמרנית במחיקה.</span>
          </div>
        </form>

        <div className="panel statusPanel">
          <div className="statusPanel__header">
            <div>
              <strong>{progress.message}</strong>
              <p className="statusHuman">{progress.human_message}</p>
            </div>
            <span>{progress.percent?.toFixed?.(1) ?? 0}%</span>
          </div>
          <div className="progressTrack">
            <div className="progressBar" style={{ width: `${progress.percent ?? 0}%` }} />
          </div>
          <div className="stagePills">
            <span className={`stagePill stagePill--${progress.stage}`}>{progress.stage}</span>
            {summary ? (
              <span className="stagePill">
                {summary.counts.safe_clusters} בטוחות · {summary.counts.review_clusters} לסקירה
              </span>
            ) : null}
          </div>
          {(summary?.degraded_flags?.warnings?.length || progress.warnings?.length) && (
            <div className="warningStack">
              {(summary?.degraded_flags?.warnings?.length ? summary.degraded_flags.warnings : progress.warnings).map(
                (warning) => (
                  <p key={warning} className="warningText">
                    {warning}
                  </p>
                ),
              )}
            </div>
          )}
          {actionMessage ? <p className="successText">{actionMessage}</p> : null}
          {error ? <p className="errorText">{error}</p> : null}
        </div>
      </aside>
      <main className="workspace">
        <section className="panel workspace__top">
          <div>
            <div className="sectionEyebrow">Review Workspace</div>
            <h2>קבוצות אלבומים</h2>
            <p>ברירת המחדל היא להוביל קודם למה שבטוח למחיקה, אבל להשאיר בכל רגע הסבר ברור למה נבחר דווקא העותק הזה.</p>
          </div>
          <div className="workspace__controls">
            <div className="tabBar">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={tab.id === selectedTab ? "tabButton tabButton--active" : "tabButton"}
                  onClick={() => setSelectedTab(tab.id)}
                  disabled={status !== "completed"}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <button className="ghostButton ghostButton--small" type="button" onClick={() => setShowShortcuts(true)}>
              קיצורי מקלדת
            </button>
          </div>
        </section>

        {successSummary ? (
          <section className="panel successPanel">
            <div>
              <div className="sectionEyebrow">Clean Moment</div>
              <h3>הספרייה התקדמה עוד צעד לסדר</h3>
              <p>
                הועברו {successSummary.moved_count} תיקיות לסל המחזור, וביחד התפנה בערך {formatSizeMb(successSummary.total_size_mb)}.
              </p>
            </div>
          </section>
        ) : null}

        <section className="contentGrid">
          <div className="clusterColumn">
            {status !== "completed" ? (
              <div className="emptyState panel">
                <h3>מוכן להתחיל</h3>
                <p>בחר תיקיות, לחץ על "התחל ניתוח", ותן למערכת להכין סביבת החלטה ברורה ובטוחה.</p>
              </div>
            ) : null}
            {status === "completed" && clusters.length === 0 ? (
              <div className="emptyState panel">
                <h3>אין תוצאות בטאב הזה</h3>
                <p>נסה לעבור ל-"כל התוצאות" או להריץ ניתוח נוסף עם תיקיות אחרות.</p>
              </div>
            ) : null}
            {clusters.map((cluster) => (
              <ClusterCard
                key={cluster.cluster_id}
                cluster={cluster}
                isActive={cluster.cluster_id === selectedClusterId}
                currentKeeperId={getCurrentKeeperId(cluster, decisions)}
                onSelect={setSelectedClusterId}
                onChooseKeeper={updateDecision}
              />
            ))}
          </div>

          <aside className="panel detailPanel">
            {selectedCluster ? (
              <>
                <div className="detailPanel__header">
                  <div>
                    <div className="sectionEyebrow">Decision Context</div>
                    <h3>השוואה חזותית</h3>
                    <p className="detailSummary">{selectedCluster.human_summary}</p>
                  </div>
                  <div className="detailPanel__badges">
                    <span className={`bucketBadge bucketBadge--${selectedCluster.confidence_bucket}`}>{bucketLabel(selectedCluster.confidence_bucket)}</span>
                    <span className={`resolutionBadge resolutionBadge--${selectedCluster.resolution_state}`}>{resolutionLabel(selectedCluster.resolution_state)}</span>
                  </div>
                </div>

                <div className="reasonPills">
                  {selectedCluster.comparison_highlights.map((highlight) => (
                    <span key={highlight.id} className={`reasonPill reasonPill--${highlight.tone}`}>
                      <strong>{toneLabel(highlight.tone)}</strong>
                      {highlight.label}
                      {highlight.value ? ` · ${highlight.value}` : ""}
                    </span>
                  ))}
                </div>

                <div className="recommendedReason">
                  <strong>למה דווקא העותק הזה?</strong>
                  <span>{selectedCluster.recommended_keeper_reason ?? "כרגע אין keeper מומלץ חד-משמעי."}</span>
                </div>

                <div className="albumsDetail albumsDetail--comparison">
                  {selectedCluster.albums.map((album) => (
                    <AlbumComparisonCard
                      key={album.folder_id}
                      album={album}
                      isKeeper={currentKeeperId === album.folder_id}
                      isFocused={focusedAlbumId === album.folder_id}
                      metricWinners={metricWinners}
                      highlights={selectedAlbumHighlights[album.folder_id] ?? []}
                      onChooseKeeper={(albumId) => {
                        setFocusedAlbumId(albumId);
                        updateDecision(selectedCluster.cluster_id, albumId);
                      }}
                      onOpenExplorer={openExplorer}
                      onDeleteNow={(targetAlbum) =>
                        setSingleDeleteTarget({
                          clusterId: selectedCluster.cluster_id,
                          folderId: targetAlbum.folder_id,
                          name: targetAlbum.name,
                        })
                      }
                      onFocus={setFocusedAlbumId}
                    />
                  ))}
                </div>

                <section className="trackComparison">
                  <div className="sectionEyebrow">Unified Tracklist</div>
                  <h4>רשימת שירים מאוחדת</h4>
                  <div className="trackComparison__table">
                    <div className="trackComparison__head trackComparison__row">
                      <span>שיר</span>
                      <span>אמן</span>
                      <span>אורך</span>
                      {selectedCluster.albums.map((album) => (
                        <span key={album.folder_id}>{album.name}</span>
                      ))}
                    </div>
                    {trackComparisonRows.map((row) => (
                      <div key={row.key} className="trackComparison__row">
                        <strong>{row.title}</strong>
                        <span>{row.artist}</span>
                        <span>{formatDuration(row.duration)}</span>
                        {selectedCluster.albums.map((album) => (
                          <span key={`${row.key}-${album.folder_id}`} className="trackPresence">
                            {album.is_deleted ? "הוסר" : row.presence[album.folder_id] ? "יש" : "חסר"}
                          </span>
                        ))}
                      </div>
                    ))}
                  </div>
                </section>

                <details className="technicalPanel">
                  <summary>מידע טכני מתקדם</summary>
                  <p className="technicalSummary">{selectedCluster.technical_summary}</p>
                  <div className="pairTable">
                    {selectedCluster.pairs.map((pair) => (
                      <div key={pair.pair_id} className="pairRow">
                        <div>
                          <strong>{formatPercent(pair.final_score)}</strong>
                          <span>סופי</span>
                        </div>
                        <div>
                          <strong>{formatPercent(pair.base_score)}</strong>
                          <span>Base</span>
                        </div>
                        <div>
                          <strong>{formatPercent(pair.algorithmic_score)}</strong>
                          <span>Algo</span>
                        </div>
                        <div>
                          <strong>{pair.ml_score !== null ? formatPercent(pair.ml_score) : "N/A"}</strong>
                          <span>ML</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              </>
            ) : (
              <div className="emptyState">
                <h3>בחר קבוצה</h3>
                <p>ברגע שתבחר cluster, תופיע כאן השוואה נקייה שמדגישה רק מה שחשוב להחלטה.</p>
              </div>
            )}
          </aside>
        </section>

        <section className="panel actionBar">
          <div>
            <div className="sectionEyebrow">Delete Preview</div>
            <h3>אישור מרוכז לפני העברה לסל המחזור</h3>
            <p>שום דבר לא יימחק לצמיתות. המערכת מרכזת כאן רק את מה שסומן למחיקה, יחד עם נפח משוער ומקור ההחלטה.</p>
          </div>
          <div className="actionBar__summary">
            <div className="deleteCount">
              <strong>{preview.total_count}</strong>
              <span>תיקיות</span>
            </div>
            <div className="previewStats">
              <div className="previewStat">
                <span>נפח משוער</span>
                <strong>{formatSizeMb(preview.total_size_mb)}</strong>
              </div>
              <div className="previewStat">
                <span>אוטומטי</span>
                <strong>{preview.auto_selected_count}</strong>
              </div>
              <div className="previewStat">
                <span>ידני</span>
                <strong>{preview.manual_selected_count}</strong>
              </div>
            </div>
            <button className="dangerButton" type="button" onClick={() => setBulkConfirmOpen(true)} disabled={preview.total_count === 0 || executingDelete}>
              {executingDelete ? "מעביר לסל..." : `אשר העברה של ${preview.total_count} תיקיות לסל המחזור`}
            </button>
          </div>
          <div className="deleteList">
            {preview.items.map((item) => (
              <div key={item.folder_id} className="deleteRow">
                <div>
                  <strong>{item.folder_name}</strong>
                  <small>יישמר: {item.keeper_folder_name} · {formatSizeMb(item.estimated_size_mb)}</small>
                </div>
                <span className={`resolutionBadge resolutionBadge--${item.selection_source}`}>{resolutionLabel(item.selection_source)}</span>
              </div>
            ))}
            {preview.total_count === 0 ? <p className="subtleText">עדיין אין פריטים שמסומנים למחיקה.</p> : null}
          </div>
        </section>
      </main>
      {showShortcuts ? <ShortcutOverlay onClose={() => setShowShortcuts(false)} /> : null}
      {bulkConfirmOpen ? (
        <ConfirmDialog
          title="להעביר את הפריטים המסומנים לסל המחזור?"
          body={`יועברו ${preview.total_count} תיקיות בנפח משוער של ${formatSizeMb(preview.total_size_mb)}. אפשר לחזור לסקירה לפני הביצוע.`}
          confirmText="כן, העבר לסל המחזור"
          tone="danger"
          onConfirm={executeDelete}
          onCancel={() => setBulkConfirmOpen(false)}
        />
      ) : null}
      {singleDeleteTarget ? (
        <ConfirmDialog
          title={`להעביר את "${singleDeleteTarget.name}" לסל המחזור?`}
          body="הפעולה מיידית, אבל עדיין בטוחה: התיקייה תועבר לסל המחזור בלבד ותוסר מרשימת הסקירה הנוכחית."
          confirmText="כן, העבר לסל המחזור"
          tone="danger"
          onConfirm={() => executeSingleDelete(singleDeleteTarget)}
          onCancel={() => setSingleDeleteTarget(null)}
        />
      ) : null}
    </div>
  );
}
