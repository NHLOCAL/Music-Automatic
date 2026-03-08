import React, { useMemo } from "react";
import { Button, Badge } from "./UI";
import {
  buildTrackComparisonRows,
  formatBitrate,
  formatDuration,
  formatSizeMb,
  getAlbumOrdinalLabel,
  getClusterDisplayTitle,
  getMetricWinners,
  getTrackFieldTone,
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
        <div style={{ color: 'var(--border-default)', marginBottom: '24px' }}>
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="3" x2="9" y2="21"></line>
          </svg>
        </div>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-main)' }}>בחר קבוצה להשוואה</h3>
        <p style={{ color: 'var(--text-secondary)', marginTop: '8px' }}>
          בחר פריט מהתפריט מימין כדי לראות את פרטי ההשוואה.
        </p>
      </div>
    );
  }

  const visibleAlbums = cluster.albums.filter((a) => !a.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const albumIds = visibleAlbums.map((album) => album.folder_id);
  const activeKeeperIndex = visibleAlbums.findIndex((album) => album.folder_id === currentKeeperId);
  const activeKeeperLabel = activeKeeperIndex >= 0 ? getAlbumOrdinalLabel(activeKeeperIndex) : null;

  const subtitleText = useMemo(() => {
    if (!activeKeeperLabel) return cluster.human_summary;
    if (cluster.confidence_bucket === "safe") {
      return `נמצאו ${visibleAlbums.length} עותקים כמעט זהים. מומלץ לשמור את ${activeKeeperLabel} ולבדוק מולו את שאר העותקים בקבוצה.`;
    }
    return `נדרשת בדיקה ידנית לפני מחיקה. ההמלצה הראשונית היא לשמור את ${activeKeeperLabel} ולהשוות מולו את שאר העותקים.`;
  }, [activeKeeperLabel, cluster.confidence_bucket, cluster.human_summary, visibleAlbums.length]);

  const renderMetric = (album, key, formatFn, unit = "") => {
    const isWinner = metricWinners[key] === album.folder_id;
    const isLoser = metricWinners[key] !== null && !isWinner;
    const rawVal = album[key];
    const valStr = formatFn(rawVal);
    
    let valueClass = "stat-val";
    if (isWinner) valueClass += " val-good";
    else if (isLoser) valueClass += ""; // Neutral/Standard

    return (
      <span className={valueClass}>
        {valStr} {unit}
      </span>
    );
  };

  const renderTrackCell = (row, albumId) => {
    const entry = row.entries[albumId];
    if (!entry) return <td className="track-cell missing-track">חסר קובץ</td>;

    const bitrateDiff = getTrackFieldTone(row, albumIds, "bitrate") === "different";
    const sizeDiff = getTrackFieldTone(row, albumIds, "size_mb") === "different";
    const durationDiff = getTrackFieldTone(row, albumIds, "duration") === "different";

    return (
      <td className="track-cell">
        <div className="td-main" title={entry.filename}>{entry.filename}</div>
        <div style={{ display: 'flex', gap: '8px', marginTop: '4px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          <span className={bitrateDiff ? "diff-highlight" : ""}>{formatBitrate(entry.bitrate)}</span>
          <span>•</span>
          <span className={sizeDiff ? "diff-highlight" : ""}>{formatSizeMb(entry.size_mb)}</span>
          <span>•</span>
          <span className={durationDiff ? "diff-highlight" : ""}>{formatDuration(entry.duration)}</span>
        </div>
      </td>
    );
  };

  return (
    <div className="workspace">
      <div className="diff-area">
        <div className="diff-header">
          <div className="diff-title">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
              <h2>{getClusterDisplayTitle(cluster)}</h2>
              <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
                {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "לסקירה"}
              </Badge>
            </div>
            <p>{subtitleText}</p>
          </div>
          <Button variant="secondary" onClick={onBackToSetup}>סריקה חדשה</Button>
        </div>

        <div className="diff-content">
          {/* Top Cards Grid */}
          <div className="comparison-grid">
            {visibleAlbums.map((album, albumIndex) => {
              const isKeeper = currentKeeperId === album.folder_id;
              const isMarked = selectedDeleteFolderIds.includes(album.folder_id);
              const isSuggestedKeeper = !hasUserDecision && cluster.recommended_keeper_id === album.folder_id;
              const albumOrdinalLabel = getAlbumOrdinalLabel(albumIndex);

              return (
                <div key={album.folder_id} className={`album-box ${isKeeper ? 'is-keeper' : ''} ${isMarked ? 'is-deleted' : ''}`}>
                  <div className="box-header">
                    <div className="box-order-row">
                      <div className="album-index-badge">{albumIndex + 1}</div>
                      <div className="album-order-label">{albumOrdinalLabel}</div>
                    </div>
                    <div className="box-title">
                       <span title={album.name}>{album.name}</span>
                       {isKeeper && <Badge tone="success">נשמר</Badge>}
                       {isMarked && <Badge tone="danger">למחיקה</Badge>}
                       {isSuggestedKeeper && !isKeeper && <Badge tone="warning">מומלץ</Badge>}
                    </div>
                    <div className="box-path" title={album.path}>{album.path}</div>
                  </div>
                  
                  <div className="box-stats">
                    <div className="stat-row">
                      <span className="stat-key">דירוג איכות</span>
                      {renderMetric(album, 'quality_score', v => v ? v.toFixed(1) : 'N/A', '%')}
                    </div>
                    <div className="stat-row">
                      <span className="stat-key">איכות שמע</span>
                      {renderMetric(album, 'avg_bitrate', v => Math.round(v), 'kbps')}
                    </div>
                    <div className="stat-row">
                      <span className="stat-key">נפח כולל</span>
                      {renderMetric(album, 'total_size_mb', formatSizeMb)}
                    </div>
                    <div className="stat-row">
                      <span className="stat-key">קבצים</span>
                      <span className="stat-val">{album.file_count}</span>
                    </div>
                    <div className="stat-row">
                      <span className="stat-key">עטיפה</span>
                      <span className={`stat-val ${album.has_album_art ? 'val-good' : ''}`}>
                        {album.has_album_art ? "יש" : "אין"}
                      </span>
                    </div>
                  </div>

                  <div className="box-actions">
                    <Button 
                      variant={isKeeper ? "success" : "secondary"} 
                      style={{ flex: 1 }} 
                      disabled={isKeeper}
                      onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                    >
                      {isKeeper ? "נבחר לשמירה" : "בחר לשמירה"}
                    </Button>
                    
                    <Button
                      variant={isMarked ? "secondary" : "ghost"}
                      title="סמן למחיקה מרוכזת"
                      disabled={isKeeper || !currentKeeperId}
                      onClick={() => toggleDeleteSelection(cluster.cluster_id, album.folder_id)}
                    >
                      {isMarked ? "בטל מחיקה" : "סמן למחיקה"}
                    </Button>

                    <Button variant="ghost" size="icon" onClick={() => openExplorer(album.path)} title="פתח תיקייה">
                       <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    </Button>
                  </div>

                  <div className="box-secondary-action">
                    {isKeeper ? (
                      <Button variant="secondary" style={{ width: "100%" }} size="sm" disabled>
                        עותק שמור
                      </Button>
                    ) : (
                      <Button 
                        variant="danger" 
                        style={{ width: '100%', opacity: 0.88 }} 
                        size="sm"
                        onClick={() => setSingleDeleteTarget({ clusterId: cluster.cluster_id, folderId: album.folder_id, name: album.name })}
                      >
                        מחק תיקייה זו כעת
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Track List */}
          <div className="track-table-container">
            <div className="track-header">
              <h3>השוואת קבצים מפורטת</h3>
              <div className="legend">
                <span><span className="dot diff"></span> שוני בנתונים</span>
                <span><span className="dot missing"></span> קובץ חסר</span>
              </div>
            </div>

            <div className="track-table-scroll">
              <table className="tracks-table">
                <thead>
                  <tr>
                    <th className="track-head-main">שיר / אמן</th>
                    {visibleAlbums.map((album, albumIndex) => (
                      <th key={album.folder_id}>
                        <div className="track-column-header">
                          <span className="track-column-index">{albumIndex + 1}</span>
                          <div className="track-column-copy">
                            <span className="track-column-label">{getAlbumOrdinalLabel(albumIndex)}</span>
                            <span className="track-column-name" title={album.name}>{album.name}</span>
                          </div>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {trackRows.length > 0 ? (
                    trackRows.map((row, rowIndex) => (
                      <tr key={row.key} className={rowIndex % 2 === 1 ? "track-row-alt" : ""}>
                        <td className="track-meta-cell">
                          <div className="td-main">{row.title}</div>
                          <div className="td-sub">{row.artist}</div>
                        </td>
                        {visibleAlbums.map((album) => (
                          <React.Fragment key={`${row.key}-${album.folder_id}`}>
                            {renderTrackCell(row, album.folder_id)}
                          </React.Fragment>
                        ))}
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="track-empty-state" colSpan={visibleAlbums.length + 1}>
                        לא נמצאו קבצי שמע להצגה בקבוצה זו.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
