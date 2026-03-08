import React, { useMemo } from "react";
import { Button, Badge } from "./UI";
import { ScoreTransparencyPanel } from "./ScoreTransparencyPanel";
import {
  buildTrackComparisonRows,
  formatBitrate,
  formatDuration,
  formatSizeMb,
  getMetricWinners,
  getTrackFieldTone,
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
        <h3 style={{ color: 'var(--text-tertiary)' }}>בחר קבוצה מהרשימה כדי להתחיל בהשוואה</h3>
      </div>
    );
  }

  const visibleAlbums = cluster.albums.filter((a) => !a.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const albumIds = visibleAlbums.map((a) => a.folder_id);

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
    if (!entry) return <td className="missing-track">חסר קובץ</td>;

    const bitrateDiff = referenceEntry && entry.bitrate !== referenceEntry.bitrate;
    const durationDiff = referenceEntry && entry.duration !== referenceEntry.duration;

    return (
      <td>
        <div className="td-main">{entry.filename}</div>
        <div style={{ display: 'flex', gap: '8px', marginTop: '4px', fontSize: '0.75rem' }}>
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

  const activeKeeperOrFirst = currentKeeperId || visibleAlbums[0]?.folder_id;

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
          <p>יש לבחור עותק אחד שישמר. שאר העותקים יסומנו אוטומטית למחיקה ויעברו לסל המחזור.</p>
        </div>
      </div>

      <div className="diff-content">
        <ScoreTransparencyPanel cluster={cluster} currentKeeperId={currentKeeperId} />

        <div className="comparison-grid">
          {visibleAlbums.map((album) => {
            const isKeeper = currentKeeperId === album.folder_id;
            const isTrash = currentKeeperId && !isKeeper;

            return (
              <div key={album.folder_id} className={`album-box ${isKeeper ? 'is-keeper' : ''} ${isTrash ? 'is-deleted' : ''}`}>
                <div className="box-header">
                  <div className="box-title">
                    <span>{album.name}</span>
                    {isKeeper && <Badge tone="success">עותק שישמר</Badge>}
                    {isTrash && <Badge tone="danger">לסל המחזור</Badge>}
                    {!currentKeeperId && cluster.recommended_keeper_id === album.folder_id && <Badge tone="warning">מומלץ</Badge>}
                  </div>
                  <div className="box-path">{album.path}</div>
                </div>

                <div className="box-stats">
                  <div className="stat-row">
                    <span className="stat-key">איכות כוללת</span>
                    {renderMetric(album, 'quality_score', v => v ? v.toFixed(1) : 'N/A')}
                  </div>
                  <div className="stat-row">
                    <span className="stat-key">ביטרייט ממוצע</span>
                    {renderMetric(album, 'avg_bitrate', v => `${Math.round(v)} kbps`)}
                  </div>
                  <div className="stat-row">
                    <span className="stat-key">נפח</span>
                    {renderMetric(album, 'total_size_mb', formatSizeMb)}
                  </div>
                  <div className="stat-row">
                    <span className="stat-key">קבצים</span>
                    <span className="stat-val">{album.file_count}</span>
                  </div>
                </div>

                <div className="box-actions">
                  <Button
                    variant={isKeeper ? "success" : "primary"}
                    style={{ flex: 1 }}
                    onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                  >
                    {isKeeper ? "נבחר לשמירה" : "בחר לשמור עותק זה"}
                  </Button>
                  <Button variant="secondary" onClick={() => openExplorer(album.path)}>
                    תיקייה
                  </Button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="track-table-container">
          <div className="track-header">
            <h3>השוואת נתוני שירים</h3>
            <span style={{fontSize: '0.8rem', color: 'var(--text-tertiary)'}}>נתונים מודגשים בצהוב מעידים על שוני מול העותק הראשי</span>
          </div>
          <div className="track-table-scroll">
            <table className="tracks-table">
              <thead>
                <tr>
                  <th>שם שיר מקורי</th>
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
                        <div className="td-sub">{row.artist}</div>
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