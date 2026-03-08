import React, { useMemo } from "react";
import { Button, Badge, Icon, VisualMetric } from "./UI";
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
        <Icon name="music" size={48} className="tone-neutral" style={{ opacity: 0.2, marginBottom: '16px' }} />
        <h3 style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>בחר קבוצה מהרשימה להתחיל</h3>
      </div>
    );
  }

  const visibleAlbums = cluster.albums.filter((a) => !a.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const activeKeeperOrFirst = currentKeeperId || visibleAlbums[0]?.folder_id;
  const selectedDeleteCount = currentKeeperId ? Math.max(visibleAlbums.length - 1, 0) : 0;

  const maxValues = useMemo(() => {
    const maxes = { quality_score: 100, avg_bitrate: 0, total_size_mb: 0, file_count: 0 };
    visibleAlbums.forEach(album => {
      maxes.avg_bitrate = Math.max(maxes.avg_bitrate, album.avg_bitrate || 0);
      maxes.total_size_mb = Math.max(maxes.total_size_mb, album.total_size_mb || 0);
      maxes.file_count = Math.max(maxes.file_count, album.file_count || 0);
    });
    return maxes;
  }, [visibleAlbums]);

  const renderTrackCell = (row, albumId, referenceEntry) => {
    const entry = row.entries[albumId];
    if (!entry) return <td className="missing-track"><Icon name="alert" size={14} /> חסר</td>;
    
    const bitrateDiff = referenceEntry && entry.bitrate !== referenceEntry.bitrate;
    const durationDiff = referenceEntry && entry.duration !== referenceEntry.duration;

    return (
      <td>
        <div className="td-main">
          <Icon name="music" size={14} className="tone-neutral" />
          {entry.filename}
        </div>
        <div style={{ display: 'flex', gap: '12px', fontSize: '0.75rem', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
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
            <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"} icon={cluster.confidence_bucket === "safe" ? "shield" : "alert"}>
              {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
            </Badge>
          </h2>
          <p>בחר עותק אחד לשמירה. שאר העותקים יסומנו להעברה לסל המחזור.</p>
        </div>
        <div className="diff-header-stats">
          <div className="diff-mini-stat">
            <Icon name="layers" size={15} />
            <div>
              <strong>{visibleAlbums.length}</strong>
              <span>עותקים</span>
            </div>
          </div>
          <div className="diff-mini-stat">
            <Icon name="music" size={15} />
            <div>
              <strong>{trackRows.length}</strong>
              <span>שירים</span>
            </div>
          </div>
          <div className="diff-mini-stat">
            <Icon name="trash" size={15} />
            <div>
              <strong>{selectedDeleteCount}</strong>
              <span>יסומנו למחיקה</span>
            </div>
          </div>
        </div>
      </div>

      <div className="diff-content">
        <ScoreTransparencyPanel cluster={cluster} currentKeeperId={currentKeeperId} />

        <section className="workspace-section">
          <div className="section-heading">
            <div>
              <span className="section-kicker">
                <Icon name="compare" size={14} />
                תצוגת השוואה
              </span>
              <h3>עותקי האלבום זה לצד זה</h3>
            </div>
            <div className="section-heading-meta">
              <Badge tone="neutral" icon="layers">{visibleAlbums.length} עותקים</Badge>
            </div>
          </div>

          <div className="comparison-grid-scroll">
            <div
              className="comparison-grid"
              style={{
                gridTemplateColumns: `repeat(${visibleAlbums.length}, minmax(260px, 1fr))`,
                minWidth: `${visibleAlbums.length * 276}px`,
              }}
            >
              {visibleAlbums.map((album, index) => {
                const isKeeper = currentKeeperId === album.folder_id;
                const isTrash = currentKeeperId && !isKeeper;
                const hasRecommendation = cluster.recommended_keeper_id === album.folder_id;

                return (
                  <div key={album.folder_id} className={`album-column ${isKeeper ? 'is-keeper' : ''} ${isTrash ? 'is-deleted' : ''}`}>
                    <div className="column-topline">
                      <Badge tone={isKeeper ? "success" : isTrash ? "danger" : "neutral"}>
                        עותק {index + 1}
                      </Badge>
                      {hasRecommendation && !isKeeper ? <Badge tone="neutral" icon="sparkle">מומלץ</Badge> : null}
                    </div>

                    <div className="column-action-bar">
                      <Button
                        variant={isKeeper ? "success" : isTrash ? "danger" : "primary"}
                        onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                      >
                        <Icon name={isKeeper ? "check-circle" : isTrash ? "trash" : "shield"} />
                        {isKeeper ? "נבחר לשמירה" : isTrash ? "מיועד למחיקה" : "שמור עותק זה"}
                      </Button>
                      <Button variant="secondary" size="icon" onClick={() => openExplorer(album.path)} title="פתח בתיקייה">
                        <Icon name="folder" />
                      </Button>
                    </div>

                    <div className="column-header-info">
                      <div className="column-title">
                        <span>{album.name}</span>
                        {isKeeper ? <Badge tone="success" icon="shield">Keeper</Badge> : null}
                      </div>
                      <div className="column-path" title={album.path}>{album.path}</div>
                      <div className="column-flags">
                        {album.in_preferred_root ? <span><Icon name="shield" size={12} /> בתיקייה מועדפת</span> : null}
                        {album.has_album_art ? <span><Icon name="eye" size={12} /> עטיפה זמינה</span> : null}
                      </div>
                    </div>

                    <div className="column-stats">
                      <VisualMetric 
                        label="דירוג איכות" 
                        value={album.quality_score ? album.quality_score.toFixed(1) : 'N/A'} 
                        percent={album.quality_score || 0}
                        tone={metricWinners.quality_score === album.folder_id ? "success" : "primary"}
                      />
                      <VisualMetric 
                        label="ביטרייט ממוצע" 
                        value={`${Math.round(album.avg_bitrate || 0)} kbps`} 
                        percent={maxValues.avg_bitrate ? ((album.avg_bitrate || 0) / maxValues.avg_bitrate) * 100 : 0}
                        tone={metricWinners.avg_bitrate === album.folder_id ? "success" : "primary"}
                      />
                      <VisualMetric 
                        label="נפח תיקייה" 
                        value={formatSizeMb(album.total_size_mb)} 
                        percent={maxValues.total_size_mb ? ((album.total_size_mb || 0) / maxValues.total_size_mb) * 100 : 0}
                        tone="neutral"
                      />
                      <VisualMetric 
                        label="מספר קבצים" 
                        value={album.file_count} 
                        percent={maxValues.file_count ? (album.file_count / maxValues.file_count) * 100 : 0}
                        tone="neutral"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="workspace-section">
          <div className="section-heading">
            <div>
              <span className="section-kicker">
                <Icon name="music" size={14} />
                תוצאות שירים
              </span>
              <h3>רשימת השוואה מפורטת</h3>
            </div>
            <div className="section-heading-meta">
              <Badge tone="neutral" icon="music">{trackRows.length} שורות</Badge>
            </div>
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
                          <div className="td-main">
                            <Icon name="music" size={14} className="tone-neutral" />
                            {row.title}
                          </div>
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
        </section>
      </div>
    </div>
  );
}
