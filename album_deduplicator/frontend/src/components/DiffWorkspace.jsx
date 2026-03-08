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
        <div style={{ color: 'var(--text-tertiary)', marginBottom: '16px' }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="3" x2="9" y2="21"></line>
          </svg>
        </div>
        <h3 style={{ color: 'var(--text-secondary)', fontSize: '1.2rem', fontWeight: 500 }}>בחר קבוצת אלבומים להשוואה</h3>
        <p style={{ color: 'var(--text-tertiary)', marginTop: '8px' }}>
          ניתן לנווט עם <kbd>↑</kbd> ו- <kbd>↓</kbd> במקלדת
        </p>
      </div>
    );
  }

  const visibleAlbums = cluster.albums.filter((a) => !a.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const albumIds = visibleAlbums.map((album) => album.folder_id);

  const trackGridStyle = {
    gridTemplateColumns: `minmax(240px, 1.2fr) repeat(${Math.max(visibleAlbums.length, 1)}, minmax(240px, 1fr))`,
  };

  const renderMetricDiff = (album, key, formatFn) => {
    const isWinner = metricWinners[key] === album.folder_id;
    const isLoser = metricWinners[key] !== null && !isWinner;
    const val = formatFn(album[key]);
    if (isWinner) return <span className="diff-value diff-positive">עדיף: {val}</span>;
    if (isLoser) return <span className="diff-value diff-negative">נחות: {val}</span>;
    return <span className="diff-value diff-neutral">זהה: {val}</span>;
  };

  const renderTrackMeta = (label, value, tone) => (
    <div className={`track-cell-meta-row track-cell-meta-row--${tone}`}>
      <span className="track-cell-meta-label">{label}</span>
      <span className="track-cell-meta-value" title={value}>{value}</span>
    </div>
  );

  return (
    <div className="workspace-main">
      <div className="workspace-header">
        <div>
          <h2>{getClusterDisplayTitle(cluster)}</h2>
          <p>{cluster.human_summary}</p>
          <div className="workspace-header-badges">
            <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
              {cluster.confidence_bucket === "safe" ? "זיהוי ודאי: בטוח למחיקה" : "זיהוי חלקי: דורש בדיקה"}
            </Badge>
            <Badge tone="neutral">{visibleAlbums.length} עותקים הושוו</Badge>
          </div>
        </div>
        <Button variant="secondary" onClick={onBackToSetup}>התחל סריקה חדשה</Button>
      </div>

      <div className="diff-container">
        <div className="cards-grid">
          {visibleAlbums.map((album) => {
            const isKeeper = currentKeeperId === album.folder_id;
            const isMarked = selectedDeleteFolderIds.includes(album.folder_id);
            const isSuggestedKeeper = !hasUserDecision && cluster.recommended_keeper_id === album.folder_id;
            
            const keeperBadge = isKeeper
              ? (cluster.resolution_state === "auto" || hasUserDecision ? "עותק נבחר לשמירה" : "עותק מומלץ לשמירה")
              : null;
            
            const keeperButtonLabel = isKeeper ? "נבחר לשמירה" : "בחר לשמירה";

            return (
              <div key={album.folder_id} className={`album-card ${isKeeper ? 'is-keeper' : ''} ${isMarked ? 'is-deleted' : ''}`}>
                <div className="card-header">
                  <div className="card-title-row">
                    <h3 title={album.name}>{album.name}</h3>
                    {keeperBadge && <Badge tone={isSuggestedKeeper ? "warning" : "success"}>{keeperBadge}</Badge>}
                    {isMarked && <Badge tone="danger">סומן למחיקה</Badge>}
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
                      title={currentKeeperId ? "סמן למחיקה מרוכזת (X)" : "יש לבחור עותק לשמירה קודם"}
                    >
                      {isMarked ? "בטל סימון" : "סמן למחיקה"}
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => openExplorer(album.path)} title="פתח בסייר הקבצים (O)">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    </Button>
                  </div>
                </div>

                <table className="diff-table">
                  <tbody>
                    <tr>
                      <td className="diff-label">דירוג איכות מומלץ</td>
                      <td>{renderMetricDiff(album, 'quality_score', v => v ? `${v.toFixed(1)}/100` : 'ללא נתון')}</td>
                    </tr>
                    <tr>
                      <td className="diff-label">איכות שמע (Bitrate)</td>
                      <td>{renderMetricDiff(album, 'avg_bitrate', v => v ? `${Math.round(v)} kbps` : 'ללא נתון')}</td>
                    </tr>
                    <tr>
                      <td className="diff-label">גודל התיקייה</td>
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
                  <div style={{ padding: '16px', background: 'var(--accent-danger-bg)', borderTop: '1px solid var(--panel-border)' }}>
                    <Button variant="danger" style={{ width: '100%' }} onClick={() => setSingleDeleteTarget({ clusterId: cluster.cluster_id, folderId: album.folder_id, name: album.name })}>
                      מחק תיקייה זו כעת (D)
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="tracklist-section">
          <div className="tracklist-header">
            <h3>השוואת רשימת שירים ונתוני קבצים</h3>
            <div className="comparison-legend">
              <div className="comparison-legend-item"><span className="legend-dot same"></span>נתונים זהים</div>
              <div className="comparison-legend-item"><span className="legend-dot different"></span>קיימים הבדלים</div>
              <div className="comparison-legend-item"><span className="legend-dot missing"></span>קובץ חסר</div>
            </div>
          </div>
          
          <div className="track-compare-table" style={trackGridStyle}>
            <div className="track-grid-header-cell">שם השיר / אמן</div>
            {visibleAlbums.map((album) => (
              <div key={album.folder_id} className="track-grid-header-cell">
                <div className="track-grid-album-name" title={album.name}>{album.name}</div>
                <div className="track-grid-album-path" title={album.path}>{album.path}</div>
              </div>
            ))}
            
            {trackRows.map((row) => {
              const rowTone = getTrackRowTone(row, albumIds);
              return (
                <React.Fragment key={row.key}>
                  <div className={`track-grid-label track-grid-label--${rowTone}`}>
                    <div className="track-grid-label-topline">
                      <div className="track-grid-title" title={row.title}>{row.title}</div>
                    </div>
                    <div className="track-grid-meta">{row.artist}</div>
                    <div className="track-grid-meta">אורך משוער: {formatDuration(row.duration)}</div>
                  </div>
                  
                  {visibleAlbums.map((album) => {
                    const entry = row.entries[album.folder_id];
                    return (
                      <div key={album.folder_id} className={`track-grid-cell ${entry ? "" : "is-missing"}`}>
                        {entry ? (
                          <div className="track-cell-meta-list">
                            {renderTrackMeta("שם קובץ", entry.filename, getTrackFieldTone(row, albumIds, "filename"))}
                            {renderTrackMeta("אורך", formatDuration(entry.duration), getTrackFieldTone(row, albumIds, "duration"))}
                            {renderTrackMeta("גודל", formatSizeMb(entry.size_mb), getTrackFieldTone(row, albumIds, "size_mb"))}
                            {renderTrackMeta("איכות שמע", formatBitrate(entry.bitrate), getTrackFieldTone(row, albumIds, "bitrate"))}
                          </div>
                        ) : (
                          "קובץ לא קיים בעותק זה"
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
  );
}