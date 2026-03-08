import React, { useMemo } from "react";
import { Badge, Button } from "./UI";
import {
  METRICS,
  buildTrackComparisonRows,
  formatMetricValue,
  getMetricWinners,
  getPairNarratives,
} from "../utils";

function MetricRow({ label, type, albums, winnerMap }) {
  const columnsStyle = {
    gridTemplateColumns: `minmax(180px, 220px) repeat(${albums.length}, minmax(180px, 1fr))`,
  };

  return (
    <div className="diff-row" style={columnsStyle}>
      <span className="diff-label">{label}</span>
      {albums.map((album) => {
        const winnerId = winnerMap;
        const isWinner = winnerId ? winnerId === album.folder_id : null;
        return (
          <div
            key={album.folder_id}
            className={`diff-val ${
              isWinner === true ? "diff-better" : isWinner === false ? "diff-worse" : "diff-neutral"
            }`}
          >
            {formatMetricValue(type, album.value)}
          </div>
        );
      })}
    </div>
  );
}

function AlbumStatus({ isKeeper, isMarkedForDelete }) {
  if (isKeeper) {
    return <Badge tone="success">נשמר</Badge>;
  }
  if (isMarkedForDelete) {
    return <Badge tone="danger">מסומן למחיקה</Badge>;
  }
  return <Badge tone="neutral">נשאר לעת עתה</Badge>;
}

export function DiffWorkspace({
  cluster,
  currentKeeperId,
  selectedDeleteFolderIds,
  focusedAlbumId,
  setFocusedAlbumId,
  handleDecision,
  toggleDeleteSelection,
  openExplorer,
  setSingleDeleteTarget,
}) {
  if (!cluster) {
    return (
      <div className="empty-workspace">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
          <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
          <line x1="12" y1="22.08" x2="12" y2="12" />
        </svg>
        <h3>בחר קבוצה כדי להתחיל</h3>
        <p>כאן תופיע השוואה ממוקדת עם פתיחה לאקספלורר, סימון למחיקה ופעולות מהירות לכל עותק.</p>
      </div>
    );
  }

  const visibleAlbums = cluster.albums.filter((album) => !album.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const pairNarratives = useMemo(() => getPairNarratives(cluster.pairs, visibleAlbums), [cluster.pairs, visibleAlbums]);
  const metricColumnsStyle = {
    gridTemplateColumns: `minmax(180px, 220px) repeat(${visibleAlbums.length}, minmax(180px, 1fr))`,
  };
  const trackColumnsStyle = {
    gridTemplateColumns: `minmax(240px, 2fr) 96px repeat(${visibleAlbums.length}, minmax(120px, 1fr))`,
  };

  return (
    <div className="diff-workspace">
      <header className="workspace-header">
        <div>
          <span className="eyebrow">לוח החלטה</span>
          <h2>{cluster.human_summary}</h2>
          <p className="workspace-description">
            בחר מה יישמר, סמן אילו עותקים יועברו לסל המחזור, ופתח כל תיקייה ישירות מאותה תצוגה.
          </p>
        </div>
        <div className="badges-row">
          <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
            {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
          </Badge>
          {cluster.reasons.map((reason) => (
            <Badge key={reason.code} tone="neutral">
              {reason.message}
            </Badge>
          ))}
        </div>
      </header>

      <div className="cluster-summary-grid">
        <div className="card summary-panel">
          <span className="panel-eyebrow">סיכום מערכת</span>
          <p>{cluster.technical_summary || "המערכת זיהתה קשר חזק בין האלבומים בקבוצה זו."}</p>
        </div>
        <div className="card summary-panel">
          <span className="panel-eyebrow">מצב נוכחי</span>
          <p>
            {currentKeeperId
              ? `${selectedDeleteFolderIds.length} תיקיות מסומנות כרגע למחיקה מתוך ${Math.max(visibleAlbums.length - 1, 0)} אפשריות.`
              : "יש לבחור קודם איזה עותק נשמר כדי לסמן עותקים אחרים למחיקה."}
          </p>
        </div>
      </div>

      <section className="comparison-section card">
        <div className="section-heading">
          <div>
            <h3>השוואה זה לצד זה</h3>
            <p>כל האלבומים בקבוצה מוצגים יחד, עם הדגשת ההבדלים החיוניים בלבד.</p>
          </div>
        </div>

        <div className="comparison-scroll">
          <div className="comparison-grid">
            <div className="album-row" style={metricColumnsStyle}>
              <div className="diff-label diff-label-head">עותק</div>
              {visibleAlbums.map((album) => {
                const isKeeper = currentKeeperId === album.folder_id;
                const isMarkedForDelete = selectedDeleteFolderIds.includes(album.folder_id);
                const isFocused = focusedAlbumId === album.folder_id;
                return (
                  <article
                    key={album.folder_id}
                    className={`album-header ${isKeeper ? "is-keeper" : ""} ${isFocused ? "is-focused" : ""}`}
                    onClick={() => setFocusedAlbumId(album.folder_id)}
                  >
                    <div className="album-title-row">
                      <h4>{album.name}</h4>
                      <AlbumStatus isKeeper={isKeeper} isMarkedForDelete={isMarkedForDelete} />
                    </div>
                    <p className="album-path">{album.path}</p>
                    <div className="album-meta">
                      <span>{formatMetricValue("count", album.file_count)} קבצים</span>
                      <span>{formatMetricValue("size", album.total_size_mb)}</span>
                    </div>
                    <div className="album-actions">
                      <Button variant={isKeeper ? "secondary" : "primary"} onClick={(event) => {
                        event.stopPropagation();
                        handleDecision(cluster.cluster_id, album.folder_id);
                      }}
                      >
                        {isKeeper ? "נבחר לשמירה" : "בחר לשמירה"}
                      </Button>
                      <Button
                        variant={isMarkedForDelete ? "secondary" : "ghost"}
                        disabled={!currentKeeperId || isKeeper}
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleDeleteSelection(cluster.cluster_id, album.folder_id);
                        }}
                      >
                        {isMarkedForDelete ? "בטל סימון" : "סמן למחיקה"}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={(event) => {
                          event.stopPropagation();
                          openExplorer(album.path);
                        }}
                      >
                        פתח תיקייה
                      </Button>
                      {!isKeeper && (
                        <Button
                          variant="danger"
                          onClick={(event) => {
                            event.stopPropagation();
                            setSingleDeleteTarget({
                              clusterId: cluster.cluster_id,
                              folderId: album.folder_id,
                              name: album.name,
                            });
                          }}
                        >
                          מחק עכשיו
                        </Button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>

            {METRICS.map((metric) => (
              <MetricRow
                key={metric.key}
                label={metric.label}
                type={metric.type}
                albums={visibleAlbums.map((album) => ({ ...album, value: album[metric.key] }))}
                winnerMap={metricWinners[metric.key]}
              />
            ))}

            <div className="diff-row" style={metricColumnsStyle}>
              <span className="diff-label">עטיפת אלבום</span>
              {visibleAlbums.map((album) => (
                <div
                  key={album.folder_id}
                  className={`diff-val ${
                    album.has_album_art ? "diff-better" : "diff-worse"
                  }`}
                >
                  {album.has_album_art ? "קיימת" : "חסרה"}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="insights-grid">
        <div className="card insights-panel">
          <div className="section-heading">
            <div>
              <h3>למה המערכת חושבת שהעותקים דומים</h3>
              <p>פירוט קצר לכל זוג שהוביל ל-cluster הזה.</p>
            </div>
          </div>
          <div className="insight-list">
            {pairNarratives.map((narrative) => (
              <div key={narrative.id} className="insight-card">
                <div className="insight-head">
                  <strong>{narrative.title}</strong>
                  <Badge tone={narrative.tone}>{narrative.scoreLabel}</Badge>
                </div>
                <p>{narrative.description}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="card insights-panel">
          <div className="section-heading">
            <div>
              <h3>הדגשות מהירות</h3>
              <p>הממצאים שהכי מקצרים את קבלת ההחלטה.</p>
            </div>
          </div>
          <div className="highlight-pill-list">
            {cluster.comparison_highlights.length ? (
              cluster.comparison_highlights.map((highlight) => (
                <span key={highlight.id} className={`highlight-pill tone-${highlight.tone}`}>
                  {highlight.label}
                  {highlight.value ? ` · ${highlight.value}` : ""}
                </span>
              ))
            ) : (
              <p>אין highlight בולט מעבר לסיכום הקבוצה.</p>
            )}
          </div>
        </div>
      </section>

      <section className="tracklist-diff-section card">
        <div className="section-heading">
          <div>
            <h3>רשימת שירים משולבת</h3>
            <p>הטבלה מדגישה במהירות שירים חסרים או חופפים בין העותקים.</p>
          </div>
        </div>
        <div className="track-scroll">
          <div className="track-table">
            <div className="track-row track-header" style={trackColumnsStyle}>
              <span>שיר</span>
              <span>אורך</span>
              {visibleAlbums.map((album) => (
                <span key={album.folder_id} className="text-center">{album.name}</span>
              ))}
            </div>
            {trackRows.map((row) => (
              <div key={row.key} className="track-row" style={trackColumnsStyle}>
                <span className="track-name">{row.title}</span>
                <span className="track-duration">{formatMetricValue("duration", row.duration)}</span>
                {visibleAlbums.map((album) => (
                  <span key={album.folder_id} className="text-center">
                    {row.presence[album.folder_id] ? <span className="icon-check">✓</span> : <span className="icon-missing">חסר</span>}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
