import React, { useMemo } from "react";
import { Button, Badge } from "./UI";
import {
  buildTrackComparisonRows,
  formatBitrate,
  formatDuration,
  formatSizeMb,
  getClusterDisplayTitle,
  getMetricWinners,
  getTrackFieldTone,
  getTrackRowTone,
} from "../utils";

export function DiffWorkspace({
  cluster,
  currentKeeperId,
  hasUserDecision,
  selectedDeleteFolderIds,
  handleDecision,
  toggleDeleteSelection,
  openExplorer,
  setSingleDeleteTarget,
  onBackToSetup,
}) {
  if (!cluster) {
    return (
      <div className="centered-view">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" color="var(--text-tertiary)" style={{ marginBottom: '16px' }}>
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="9" y1="3" x2="9" y2="21"></line>
        </svg>
        <h3 style={{ color: 'var(--text-secondary)' }}>בחר קבוצה להשוואה מתוך הרשימה</h3>
        <p style={{ color: 'var(--text-tertiary)', marginTop: '8px', fontSize: '0.875rem' }}>
          ניתן לנווט עם <kbd>↑</kbd> <kbd>↓</kbd>
        </p>
      </div>
    );
  }

  const visibleAlbums = cluster.albums.filter((a) => !a.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const albumIds = visibleAlbums.map((album) => album.folder_id);
  const trackGridStyle = {
    gridTemplateColumns: `minmax(220px, 1.1fr) repeat(${Math.max(visibleAlbums.length, 1)}, minmax(220px, 1fr))`,
  };

  const renderMetricDiff = (album, key, formatFn) => {
    const isWinner = metricWinners[key] === album.folder_id;
    const isLoser = metricWinners[key] !== null && !isWinner;
    const val = formatFn(album[key]);
    
    if (isWinner) return <span className="diff-value diff-positive">טוב יותר: {val}</span>;
    if (isLoser) return <span className="diff-value diff-negative">נמוך יותר: {val}</span>;
    return <span className="diff-value diff-neutral">זהה: {val}</span>;
  };

  const renderTrackMeta = (label, value, tone) => (
    <div className={`track-cell-meta-row track-cell-meta-row--${tone}`}>
      <span className="track-cell-meta-label">{label}</span>
      <span className="track-cell-meta-value">{value}</span>
    </div>
  );

  return (
    <div className="workspace-main">
      <div className="workspace-header">
        <div className="workspace-toolbar">
          <div>
            <h2>{getClusterDisplayTitle(cluster)}</h2>
            <p>{cluster.human_summary}</p>
            <div className="workspace-header-badges">
              <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
                {cluster.confidence_bucket === "safe" ? "אפשר למחוק בביטחון גבוה" : "נדרשת בדיקה קצרה"}
              </Badge>
              <Badge tone="neutral">{visibleAlbums.length} עותקים להשוואה</Badge>
              <Badge tone="neutral">{selectedDeleteFolderIds.length} יסומנו לסל המחזור</Badge>
            </div>
          </div>
          <Button variant="secondary" onClick={onBackToSetup}>סריקה חדשה</Button>
        </div>
      </div>
      <div className="diff-container">
        <div className="cards-grid">
          {visibleAlbums.map((album) => {
            const isKeeper = currentKeeperId === album.folder_id;
            const isMarked = selectedDeleteFolderIds.includes(album.folder_id);
            const isSuggestedKeeper = !hasUserDecision && cluster.recommended_keeper_id === album.folder_id;
            const keeperBadge = isKeeper
              ? (cluster.resolution_state === "auto" || hasUserDecision ? "נשמר" : "מומלץ לשמירה")
              : null;
            const keeperButtonLabel = isKeeper
              ? (cluster.resolution_state === "auto" || hasUserDecision ? "נבחר לשמירה" : "אשר לשמירה")
              : "בחר לשמירה";

            return (
              <div key={album.folder_id} className={`album-card ${isKeeper ? 'is-keeper' : ''} ${isMarked ? 'is-deleted' : ''}`}>
                <div className="card-header">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <h3 title={album.name}>{album.name}</h3>
                    {keeperBadge && <Badge tone={isSuggestedKeeper ? "warning" : "success"}>{keeperBadge}</Badge>}
                    {isMarked && <Badge tone="danger">מסומן למחיקה</Badge>}
                  </div>
                  <div className="card-path" title={album.path}>{album.path}</div>
                  <div className="card-actions">
                    <Button variant={isKeeper ? "secondary" : "primary"} style={{ flex: 1 }} onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}>
                      {keeperButtonLabel}
                    </Button>
                    <Button
                      variant={isMarked ? "secondary" : "ghost"}
                      disabled={isKeeper || !currentKeeperId}
                      onClick={() => toggleDeleteSelection(cluster.cluster_id, album.folder_id)}
                      title={currentKeeperId ? "סמן למחיקה (X)" : "בחר עותק לשמירה לפני סימון למחיקה"}
                    >
                      {isMarked ? "בטל סימון" : "סמן למחיקה"}
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => openExplorer(album.path)} title="פתח סייר (O)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    </Button>
                  </div>
                </div>
                
                <table className="diff-table">
                  <tbody>
                    <tr>
                      <td className="diff-label">איכות כללית</td>
                      <td>{renderMetricDiff(album, 'quality_score', v => v ? `${v.toFixed(1)}%` : 'ללא נתון')}</td>
                    </tr>
                    <tr>
                      <td className="diff-label">קצב נתונים ממוצע</td>
                      <td>{renderMetricDiff(album, 'avg_bitrate', v => v ? `${Math.round(v)} kbps` : 'ללא נתון')}</td>
                    </tr>
                    <tr>
                      <td className="diff-label">גודל כולל</td>
                      <td>{renderMetricDiff(album, 'total_size_mb', formatSizeMb)}</td>
                    </tr>
                    <tr>
                      <td className="diff-label">עטיפת אלבום</td>
                      <td>
                        <span className={`diff-value ${album.has_album_art ? 'diff-positive' : 'diff-negative'}`}>
                          {album.has_album_art ? "קיימת" : "חסרה"}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
                
                {!isKeeper && isMarked && (
                  <div style={{ padding: '16px', background: 'var(--sidebar-bg)', borderTop: '1px solid var(--panel-border)', borderRadius: '0 0 var(--radius-md) var(--radius-md)' }}>
                    <Button variant="danger" style={{ width: '100%' }} onClick={() => setSingleDeleteTarget({ clusterId: cluster.cluster_id, folderId: album.folder_id, name: album.name })}>
                      מחק עכשיו (D)
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="tracklist-section">
          <div className="tracklist-header">
            <div>
              <span>רשימת שירים והבדלים</span>
              <span className="tracklist-caption">כל עמודה מציגה את נתוני הפריט באותו מיקום בכל עותק.</span>
            </div>
            <div className="comparison-legend">
              <span className="comparison-legend-item is-same">זהה</span>
              <span className="comparison-legend-item is-different">שונה</span>
              <span className="comparison-legend-item is-missing">חסר</span>
            </div>
          </div>
          <div className="tracklist-table-shell">
            <div className="track-compare-table" style={trackGridStyle}>
              <div className="track-grid-header-cell">מיקום / שיר</div>
              {visibleAlbums.map((album) => (
                <div key={album.folder_id} className="track-grid-header-cell">
                  <div className="track-grid-album-name">{album.name}</div>
                  <div className="track-grid-album-path" title={album.path}>{album.path}</div>
                </div>
              ))}

              {trackRows.map((row) => {
                const rowTone = getTrackRowTone(row, albumIds);

                return (
                  <React.Fragment key={row.key}>
                    <div className={`track-grid-label track-grid-label--${rowTone}`}>
                      <div className="track-grid-label-topline">
                        <div className="track-grid-title">{row.title}</div>
                        <span className={`track-grid-state track-grid-state--${rowTone}`}>
                          {rowTone === "same" ? "כל הפרטים זהים" : "יש הבדלים בין העותקים"}
                        </span>
                      </div>
                      <div className="track-grid-meta">{row.artist}</div>
                      <div className="track-grid-meta">{formatDuration(row.duration)}</div>
                    </div>
                    {visibleAlbums.map((album) => {
                      const entry = row.entries[album.folder_id];

                      return (
                        <div key={album.folder_id} className={`track-grid-cell ${entry ? "" : "is-missing"}`}>
                          {entry ? (
                            <>
                              <div className="track-cell-title">{entry.title}</div>
                              {renderTrackMeta("שם קובץ", entry.filename, getTrackFieldTone(row, albumIds, "filename"))}
                              {renderTrackMeta("אורך", formatDuration(entry.duration), getTrackFieldTone(row, albumIds, "duration"))}
                              {renderTrackMeta("גודל", formatSizeMb(entry.size_mb), getTrackFieldTone(row, albumIds, "size_mb"))}
                              {renderTrackMeta("קצב נתונים", formatBitrate(entry.bitrate), getTrackFieldTone(row, albumIds, "bitrate"))}
                            </>
                          ) : (
                            <span className="status-missing">חסר בעותק זה</span>
                          )}
                        </div>
                      );
                    })}
                  </React.Fragment>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
