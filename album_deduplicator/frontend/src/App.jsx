import { useEffect, useMemo, useState, startTransition } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const TABS = [
  { id: "safe", label: "בטוח למחיקה" },
  { id: "review", label: "דורש סקירה" },
  { id: "all", label: "כל התוצאות" },
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
  return response.json();
}

function formatPercent(value) {
  if (value === null || value === undefined) return "N/A";
  return `${Number(value).toFixed(1)}%`;
}

function formatDuration(value) {
  if (!value) return "N/A";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function hydrateDecisions(clusters, previous) {
  const next = { ...previous };
  clusters.forEach((cluster) => {
    if (!(cluster.cluster_id in next)) {
      next[cluster.cluster_id] = cluster.confidence_bucket === "safe" ? cluster.recommended_keeper_id : null;
    }
  });
  return next;
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
  const [progress, setProgress] = useState({ step: "idle", message: "ממתין", percent: 0, current: 0, total: 1 });
  const [summary, setSummary] = useState(null);
  const [selectedTab, setSelectedTab] = useState("safe");
  const [clusters, setClusters] = useState([]);
  const [decisions, setDecisions] = useState({});
  const [preview, setPreview] = useState({ items: [], total_count: 0 });
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [executingDelete, setExecutingDelete] = useState(false);

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

    events.addEventListener("end", () => {
      events.close();
    });

    return () => events.close();
  }, [sessionId, selectedTab]);

  useEffect(() => {
    if (!sessionId || status !== "completed") return;
    refreshClusters(sessionId, selectedTab);
  }, [selectedTab, sessionId, status]);

  async function refreshSession(currentSessionId) {
    const data = await requestJson(`/api/analysis-sessions/${currentSessionId}`);
    setSummary(data);
    setProgress(data.progress);
  }

  async function refreshClusters(currentSessionId, bucket) {
    const data = await requestJson(`/api/analysis-sessions/${currentSessionId}/clusters?bucket=${bucket}`);
    startTransition(() => {
      setClusters(data.clusters);
      setSelectedClusterId((prev) =>
        data.clusters.some((cluster) => cluster.cluster_id === prev) ? prev : data.clusters[0]?.cluster_id ?? null,
      );
      setDecisions((prev) => hydrateDecisions(data.clusters, prev));
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
      setPreview({ items: [], total_count: 0 });
      setDecisions({});
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
      await refreshPreview(sessionId);
      alert(`הועברו ${execution.moved_count} תיקיות לסל המחזור.`);
    } catch (executionError) {
      setError(executionError.message);
    } finally {
      setExecutingDelete(false);
    }
  }

  const selectedCluster = useMemo(
    () => clusters.find((cluster) => cluster.cluster_id === selectedClusterId) ?? null,
    [clusters, selectedClusterId],
  );

  return (
    <div className="shell">
      <aside className="hero">
        <div className="hero__eyebrow">Music Automatic / Album Deduplicator</div>
        <h1>מחיקה בטוחה, עם מינימום החלטות ידניות</h1>
        <p className="hero__lead">
          הזרימה החדשה מניחה ML פעיל כברירת מחדל, משלבת אותו עם הניקוד המתמטי, ומרכזת למחיקה
          אוטומטית רק קבוצות עם ודאות גבוהה מאוד.
        </p>

        <form className="panel panel--glass" onSubmit={handleSubmit}>
          <label className="field">
            <span>תיקיות קלט</span>
            <textarea
              rows={6}
              placeholder={"C:\\Music\nD:\\Archive"}
              value={form.folders}
              onChange={(event) => setForm((current) => ({ ...current, folders: event.target.value }))}
            />
          </label>

          <label className="field">
            <span>תיקיית root מועדפת</span>
            <input
              type="text"
              placeholder="אופציונלי, חייב להיות אחת מתיקיות הקלט"
              value={form.preferred_root}
              onChange={(event) => setForm((current) => ({ ...current, preferred_root: event.target.value }))}
            />
          </label>

          <div className="actionRow">
            <button className="primaryButton" type="submit" disabled={loading}>
              {loading ? "מתחיל ניתוח..." : "התחל ניתוח"}
            </button>
            <button
              className="ghostButton"
              type="button"
              onClick={() => setAdvancedOpen((current) => !current)}
            >
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
            <span>הניקוד הסופי תמיד משלב algorithmic score + local ML.</span>
          </div>
        </form>

        <div className="panel statusPanel">
          <div className="statusPanel__header">
            <strong>{progress.message}</strong>
            <span>{progress.percent?.toFixed?.(1) ?? 0}%</span>
          </div>
          <div className="progressTrack">
            <div className="progressBar" style={{ width: `${progress.percent ?? 0}%` }} />
          </div>
          {summary ? (
            <div className="statusMeta">
              <span>{summary.counts.folders} תיקיות</span>
              <span>{summary.counts.safe_clusters} קבוצות בטוחות</span>
              <span>{summary.counts.review_clusters} קבוצות לסקירה</span>
            </div>
          ) : null}
          {summary?.degraded_flags?.warnings?.length ? (
            <div className="warningStack">
              {summary.degraded_flags.warnings.map((warning) => (
                <p key={warning} className="warningText">
                  {warning}
                </p>
              ))}
            </div>
          ) : null}
          {error ? <p className="errorText">{error}</p> : null}
        </div>
      </aside>

      <main className="workspace">
        <section className="panel workspace__top">
          <div>
            <div className="sectionEyebrow">Review Flow</div>
            <h2>קבוצות אלבומים</h2>
            <p>
              הממשק מסווג אוטומטית לקבוצות בטוחות למחיקה, קבוצות לסקירה, וכל התוצאות. ברירת
              המחדל היא להוביל אותך קודם כל למה שבטוח.
            </p>
          </div>

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
        </section>

        <section className="contentGrid">
          <div className="clusterColumn">
            {status !== "completed" ? (
              <div className="emptyState panel">
                <h3>מוכן להתחיל</h3>
                <p>הזן תיקיות ולחץ על "התחל ניתוח". התוצאות יופיעו כאן לפי clusters.</p>
              </div>
            ) : null}

            {status === "completed" && clusters.length === 0 ? (
              <div className="emptyState panel">
                <h3>אין תוצאות בטאב הזה</h3>
                <p>נסה לעבור ל-"כל התוצאות" או להריץ ניתוח נוסף עם מקורות אחרים.</p>
              </div>
            ) : null}

            {clusters.map((cluster) => {
              const currentKeeperId =
                decisions[cluster.cluster_id] !== undefined
                  ? decisions[cluster.cluster_id]
                  : cluster.confidence_bucket === "safe"
                    ? cluster.recommended_keeper_id
                    : null;

              return (
                <article
                  key={cluster.cluster_id}
                  className={
                    cluster.cluster_id === selectedClusterId ? "clusterCard clusterCard--active" : "clusterCard"
                  }
                  onClick={() => setSelectedClusterId(cluster.cluster_id)}
                >
                  <div className="clusterCard__header">
                    <div>
                      <span className={`bucketBadge bucketBadge--${cluster.confidence_bucket}`}>
                        {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
                      </span>
                      <h3>{cluster.albums.map((album) => album.name).join(" / ")}</h3>
                    </div>
                    <div className="clusterScores">
                      {cluster.pairs.map((pair) => (
                        <span key={pair.pair_id}>{formatPercent(pair.final_score)}</span>
                      ))}
                    </div>
                  </div>

                  <p className="clusterReasons">{cluster.reasons.map((reason) => reason.message).join(" ")}</p>

                  <div className="albumChoiceList">
                    {cluster.albums.map((album) => (
                      <button
                        key={album.folder_id}
                        type="button"
                        className={
                          currentKeeperId === album.folder_id ? "albumChoice albumChoice--selected" : "albumChoice"
                        }
                        onClick={(event) => {
                          event.stopPropagation();
                          updateDecision(cluster.cluster_id, album.folder_id);
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
                        updateDecision(cluster.cluster_id, null);
                      }}
                    >
                      דלג
                    </button>
                  </div>
                </article>
              );
            })}
          </div>

          <aside className="panel detailPanel">
            {selectedCluster ? (
              <>
                <div className="detailPanel__header">
                  <div>
                    <div className="sectionEyebrow">Decision Context</div>
                    <h3>פירוט קבוצה</h3>
                  </div>
                  <span className={`bucketBadge bucketBadge--${selectedCluster.confidence_bucket}`}>
                    {selectedCluster.confidence_bucket === "safe" ? "Safe" : "Review"}
                  </span>
                </div>

                <div className="reasonPills">
                  {selectedCluster.reasons.map((reason) => (
                    <span key={reason.code} className="reasonPill">
                      {reason.message}
                    </span>
                  ))}
                </div>

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

                <div className="albumsDetail">
                  {selectedCluster.albums.map((album) => (
                    <section key={album.folder_id} className="albumPanel">
                      <header>
                        <h4>{album.name}</h4>
                        <div className="albumMeta">
                          <span>איכות {formatPercent(album.quality_score)}</span>
                          <span>{album.file_count} שירים</span>
                          <span>{Math.round(album.avg_bitrate || 0)} kbps</span>
                        </div>
                      </header>

                      <div className="trackList">
                        {album.tracks.map((track) => (
                          <div key={`${album.folder_id}-${track.filename}`} className="trackRow">
                            <strong>{track.title || track.filename}</strong>
                            <span>{track.artist || "ללא אמן"}</span>
                            <span>{formatDuration(track.duration)}</span>
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              </>
            ) : (
              <div className="emptyState">
                <h3>בחר קבוצה</h3>
                <p>לחיצה על cluster תציג כאן את כל ההקשר הדרוש להחלטה.</p>
              </div>
            )}
          </aside>
        </section>

        <section className="panel deletePanel">
          <div>
            <div className="sectionEyebrow">Delete Preview</div>
            <h3>אישור מחיקה מרוכז</h3>
            <p>
              הפעולה תעביר תיקיות ל-Recycle Bin בלבד. ברירת המחדל כוללת רק קבוצות שסווגו כבטוחות,
              אלא אם בחרת keeper ידני לקבוצות review.
            </p>
          </div>

          <div className="deletePanel__body">
            <div className="deleteCount">{preview.total_count}</div>
            <div className="deleteList">
              {preview.items.map((item) => (
                <div key={item.folder_id} className="deleteRow">
                  <span>{item.folder_name}</span>
                  <small>יישמר: {item.keeper_folder_name}</small>
                </div>
              ))}
              {preview.total_count === 0 ? <p>עדיין אין תיקיות שנבחרו למחיקה.</p> : null}
            </div>
            <button
              className="dangerButton"
              type="button"
              onClick={executeDelete}
              disabled={preview.total_count === 0 || executingDelete}
            >
              {executingDelete ? "מעביר לסל..." : `אשר העברה של ${preview.total_count} תיקיות לסל המחזור`}
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
