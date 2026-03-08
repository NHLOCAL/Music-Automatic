import React, { useMemo } from "react";
import { Button, Badge } from "./UI";
import { buildTrackComparisonRows, formatSizeMb, getMetricWinners } from "../utils";

export function DiffWorkspace({ cluster, currentKeeperId, selectedDeleteFolderIds, handleDecision, toggleDeleteSelection, openExplorer, setSingleDeleteTarget }) {
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

  const renderMetricDiff = (album, key, formatFn) => {
    const isWinner = metricWinners[key] === album.folder_id;
    const isLoser = metricWinners[key] !== null && !isWinner;
    const val = formatFn(album[key]);
    
    if (isWinner) return <span className="diff-value diff-positive">{val}</span>;
    if (isLoser) return <span className="diff-value diff-negative">{val}</span>;
    return <span className="diff-value">{val}</span>;
  };

  return (
    <div className="workspace-main">
      <div className="workspace-header">
        <h2>השוואת נתונים</h2>
        <p>{cluster.human_summary}</p>
      </div>
      <div className="diff-container">
        <div className="cards-grid">
          {visibleAlbums.map((album) => {
            const isKeeper = currentKeeperId === album.folder_id;
            const isMarked = selectedDeleteFolderIds.includes(album.folder_id);

            return (
              <div key={album.folder_id} className={`album-card ${isKeeper ? 'is-keeper' : ''} ${isMarked ? 'is-deleted' : ''}`}>
                <div className="card-header">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <h3 title={album.name}>{album.name}</h3>
                    {isKeeper && <Badge tone="success">נשמר</Badge>}
                    {isMarked && <Badge tone="danger">מסומן למחיקה</Badge>}
                  </div>
                  <div className="card-path" title={album.path}>{album.path}</div>
                  <div className="card-actions">
                    <Button variant={isKeeper ? "secondary" : "primary"} style={{ flex: 1 }} onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}>
                      {isKeeper ? "נבחר כשומר" : "הגדר כשומר"}
                    </Button>
                    <Button variant={isMarked ? "secondary" : "ghost"} disabled={isKeeper} onClick={() => toggleDeleteSelection(cluster.cluster_id, album.folder_id)} title="סמן למחיקה (X)">
                      {isMarked ? "בטל מחיקה" : "סמן למחיקה"}
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => openExplorer(album.path)} title="פתח סייר (O)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    </Button>
                  </div>
                </div>
                
                <table className="diff-table">
                  <tbody>
                    <tr>
                      <td className="diff-label">איכות משוקללת</td>
                      <td>{renderMetricDiff(album, 'quality_score', v => v ? `${v.toFixed(1)}%` : 'N/A')}</td>
                    </tr>
                    <tr>
                      <td className="diff-label">ביטרייט</td>
                      <td>{renderMetricDiff(album, 'avg_bitrate', v => v ? `${Math.round(v)} kbps` : 'N/A')}</td>
                    </tr>
                    <tr>
                      <td className="diff-label">נפח כולל</td>
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
          <div className="tracklist-header">רשימת שירים והבדלים</div>
          <div style={{ background: 'var(--surface-bg)', border: '1px solid var(--panel-border)', borderRadius: 'var(--radius-md)' }}>
            {trackRows.map(row => (
              <div key={row.key} className="track-row">
                <div className="track-name">{row.title}</div>
                {visibleAlbums.map(album => (
                  <div key={album.folder_id} className="track-status">
                    {row.presence[album.folder_id] ? (
                      <span className="status-ok">✓ קיים</span>
                    ) : (
                      <span className="status-missing">חסר</span>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}