import React, { useMemo } from "react";
import { Badge, Button } from "./UI";
import { buildTrackComparisonRows, formatSizeMb, getMetricWinners } from "../utils";

function formatBitrate(val) { return val ? `${Math.round(val)} kbps` : 'N/A'; }
function formatRatio(val) { return val !== null ? `${Math.round(val * 100)}%` : 'N/A'; }

export function DiffWorkspace({
  cluster,
  currentKeeperId,
  selectedDeleteFolderIds,
  handleDecision,
  toggleDeleteSelection,
  openExplorer,
  setSingleDeleteTarget,
}) {
  if (!cluster) {
    return (
      <div className="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M4 19V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14M16 3v18M8 3v18M4 12h16" />
        </svg>
        <h3>בחר קבוצת אלבומים להשוואה</h3>
        <p>השתמש בחצים במקלדת כדי לנווט, <kbd>Space</kbd> לדילוג.</p>
      </div>
    );
  }

  const visibleAlbums = cluster.albums.filter((album) => !album.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);

  return (
    <div className="diff-workspace">
      <div className="diff-header">
        <h2>השוואת עותקים</h2>
        <div className="diff-header-meta">
           <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
            {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
          </Badge>
          <p>{cluster.human_summary}</p>
        </div>
      </div>

      <div className="diff-grid">
        {visibleAlbums.map((album) => {
          const isKeeper = currentKeeperId === album.folder_id;
          const isMarkedForDelete = selectedDeleteFolderIds.includes(album.folder_id);

          return (
            <div key={album.folder_id} className={`album-card ${isKeeper ? 'is-keeper' : ''} ${isMarkedForDelete ? 'is-deleted' : ''}`}>
              <div className="album-card-header">
                <div className="album-title-wrap">
                  <h4>{album.name}</h4>
                  {isKeeper && <Badge tone="success">נשמר</Badge>}
                  {isMarkedForDelete && <Badge tone="danger">מסומן למחיקה</Badge>}
                </div>
                <div className="album-path">{album.path}</div>
                <div className="album-actions">
                  <Button 
                    variant={isKeeper ? "secondary" : "primary"} 
                    onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                  >
                    {isKeeper ? "נבחר" : "בחר כשומר"}
                  </Button>
                  <Button 
                    variant={isMarkedForDelete ? "secondary" : "ghost"}
                    disabled={isKeeper}
                    onClick={() => toggleDeleteSelection(cluster.cluster_id, album.folder_id)}
                  >
                    {isMarkedForDelete ? "בטל מחיקה" : "סמן למחיקה"} <kbd>X</kbd>
                  </Button>
                  <Button variant="ghost" onClick={() => openExplorer(album.path)} title="פתח סייר">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                  </Button>
                </div>
              </div>

              <div className="metrics-list">
                <div className="metric-row">
                  <span className="metric-label">איכות</span>
                  <span className={`metric-value ${metricWinners['quality_score'] === album.folder_id ? 'positive' : ''}`}>
                    {album.quality_score ? `${album.quality_score.toFixed(1)}%` : 'N/A'}
                  </span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">ביטרייט</span>
                  <span className={`metric-value ${metricWinners['avg_bitrate'] === album.folder_id ? 'positive' : ''}`}>
                    {formatBitrate(album.avg_bitrate)}
                  </span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">משקל כולל</span>
                  <span className="metric-value">{formatSizeMb(album.total_size_mb)}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">קובצי מוזיקה</span>
                  <span className="metric-value">{album.file_count}</span>
                </div>
                 <div className="metric-row">
                  <span className="metric-label">עטיפת אלבום</span>
                  <span className={`metric-value ${album.has_album_art ? 'positive' : 'negative'}`}>
                    {album.has_album_art ? "קיימת" : "חסרה"}
                  </span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Lossless</span>
                  <span className="metric-value">{formatRatio(album.lossless_ratio)}</span>
                </div>
              </div>
              
              {!isKeeper && isMarkedForDelete && (
                <div style={{ padding: '0 20px 20px' }}>
                   <Button variant="danger" style={{ width: '100%' }} onClick={() => setSingleDeleteTarget({ clusterId: cluster.cluster_id, folderId: album.folder_id, name: album.name })}>
                      מחק עכשיו
                   </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="tracklist-section">
        <div className="tracklist-header">השוואת רשימת שירים (הדגשת חוסרים)</div>
        <table className="track-table">
          <thead>
            <tr>
              <th style={{ textAlign: 'right' }}>שם שיר</th>
              {visibleAlbums.map(album => (
                <th key={album.folder_id}>{album.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trackRows.map(row => (
              <tr key={row.key}>
                <td>{row.title}</td>
                {visibleAlbums.map(album => (
                  <td key={album.folder_id}>
                    {row.presence[album.folder_id] ? (
                      <span className="track-presence exists">✓</span>
                    ) : (
                      <span className="track-presence missing">חסר</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}