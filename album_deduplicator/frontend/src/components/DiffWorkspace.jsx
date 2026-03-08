import React, { useMemo } from "react";
import { Button, Badge } from "./UI";
import { ScoreTransparencyPanel } from "./ScoreTransparencyPanel";
import {
  buildTrackComparisonRows,
  formatBitrate,
  formatDuration,
  formatSizeMb,
  getMetricWinners,
} from "../utils";
export function DiffWorkspace({
  cluster,
  currentKeeperId,
  handleDecision,
  openExplorer,
}) {
  if (!cluster) {
    return (
      <div className="centered-view">
        <h3 style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>בחר קבוצה מהרשימה להתחיל</h3>
      </div>
    );
  }
  const visibleAlbums = cluster.albums.filter((a) => !a.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const activeKeeperOrFirst = currentKeeperId || visibleAlbums[0]?.folder_id;
  const renderMetric = (album, key, formatFn) => {
    const isWinner = metricWinners[key] === album.folder_id;
    return (
      <span className={`stat-val ${isWinner ? "val-good" : ""}`}>
        {formatFn(album[key])}
      </span>
    );
  };
  const renderTrackCell = (row, albumId, referenceEntry) => {
    const entry = row.entries[albumId];
    if (!entry) return <td className="missing-track">חסר</td>;
    const bitrateDiff = referenceEntry && entry.bitrate !== referenceEntry.bitrate;
    const durationDiff = referenceEntry && entry.duration !== referenceEntry.duration;
    return (
      <td>
        <div className="td-main">{entry.filename}</div>
        <div style={{ display: 'flex', gap: '8px', fontSize: '0.75rem', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
          <span className={bitrateDiff ? "diff-highlight" : "diff-dimmed"}>
            {formatBitrate(entry.bitrate)}
          </span>
          <span className={durationDiff ? "diff-highlight" : "diff-dimmed"}>
            {formatDuration(entry.duration)}
          </span>
        </div>
      </td>
    );
  };
  return (
    <div className="diff-area">
      <div className="diff-header">
        <div className="diff-title">
          <h2>
            {cluster.human_summary}
            <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
              {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
            </Badge>
          </h2>
          <p>בחר עותק אחד לשמירה. שאר העותקים יסומנו להעברה לסל המחזור.</p>
        </div>
      </div>
      <div className="diff-content">
        <ScoreTransparencyPanel cluster={cluster} currentKeeperId={currentKeeperId} />
        <div className="comparison-grid">
          {visibleAlbums.map((album) => {
            const isKeeper = currentKeeperId === album.folder_id;
            const isTrash = currentKeeperId && !isKeeper;
            return (
              <div key={album.folder_id} className={`album-column ${isKeeper ? 'is-keeper' : ''} ${isTrash ? 'is-deleted' : ''}`}>
                <div className="column-action-bar">
                  <Button
                    variant={isKeeper ? "success" : isTrash ? "danger" : "primary"}
                    onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                  >
                    {isKeeper ? "✓ נבחר לשמירה" : isTrash ? "✗ מיועד למחיקה" : "שמור עותק זה"}
                  </Button>
                  <Button variant="secondary" onClick={() => openExplorer(album.path)}>
                    תיקייה
                  </Button>
                </div>
                <div className="column-header-info">
                  <div className="column-title">
                    <span>{album.name}</span>
                    {!currentKeeperId && cluster.recommended_keeper_id === album.folder_id && <Badge tone="neutral">מומלץ</Badge>}
                  </div>
                  <div className="column-path" title={album.path}>{album.path}</div>
                </div>
                <div className="column-stats">
                  <div className="stat-row">
                    <span className="stat-key">דירוג איכות</span>
                    {renderMetric(album, 'quality_score', v => v ? v.toFixed(1) : 'N/A')}
                  </div>
                  <div className="stat-row">
                    <span className="stat-key">ביטרייט ממוצע</span>
                    {renderMetric(album, 'avg_bitrate', v => `${Math.round(v)} kbps`)}
                  </div>
                  <div className="stat-row">
                    <span className="stat-key">נפח תיקייה</span>
                    {renderMetric(album, 'total_size_mb', formatSizeMb)}
                  </div>
                  <div className="stat-row">
                    <span className="stat-key">מספר קבצים</span>
                    <span className="stat-val">{album.file_count}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="track-table-container">
          <div className="track-table-scroll">
            <table className="tracks-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'right' }}>שיר מקורי</th>
                  {visibleAlbums.map(a => <th key={a.folder_id}>{a.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {trackRows.map(row => {
                  const referenceEntry = row.entries[activeKeeperOrFirst];
                  return (
                    <tr key={row.key}>
                      <td className="track-meta-cell">
                        <div className="td-main">{row.title}</div>
                      </td>
                      {visibleAlbums.map(album => (
                        <React.Fragment key={`${row.key}-${album.folder_id}`}>
                          {renderTrackCell(row, album.folder_id, referenceEntry)}
                        </React.Fragment>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}