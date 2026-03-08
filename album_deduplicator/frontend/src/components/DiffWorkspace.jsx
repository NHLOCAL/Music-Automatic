import React, { useMemo } from "react";
import { Button, Badge } from "./UI";
import { METRICS, formatMetricValue, buildTrackComparisonRows, getMetricWinners } from "../utils";
function VisualDiffRow({ label, valA, valB, type, isWinnerA, isWinnerB }) {
  const getDiffClass = (isWinner) => {
    if (isWinner === true) return "diff-val diff-better";
    if (isWinner === false) return "diff-val diff-worse";
    return "diff-val diff-neutral";
  };
  return (
    <div className="diff-row">
      <span className="diff-label">{label}</span>
      <div className={getDiffClass(isWinnerA)}>{formatMetricValue(type, valA)}</div>
      <div className={getDiffClass(isWinnerB)}>{formatMetricValue(type, valB)}</div>
    </div>
  );
}
export function DiffWorkspace({ cluster, currentKeeperId, focusedAlbumId, setFocusedAlbumId, handleDecision, openExplorer, setSingleDeleteTarget }) {
  if (!cluster) {
    return (
      <div className="empty-workspace">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
        <h3>בחר קבוצה כדי להתחיל</h3>
        <p>ההשוואה הויזואלית תופיע כאן, עם הדגשה של ההבדלים החשובים בלבד.</p>
      </div>
    );
  }
  const visibleAlbums = cluster.albums.filter(a => !a.is_deleted);
  const metricWinners = useMemo(() => getMetricWinners(visibleAlbums), [visibleAlbums]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const albumA = visibleAlbums[0];
  const albumB = visibleAlbums[1]; 
  return (
    <div className="diff-workspace">
      <header className="workspace-header">
        <div>
          <span className="eyebrow">השוואת פריטים</span>
          <h2>{cluster.human_summary}</h2>
        </div>
        <div className="badges-row">
          <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
            {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
          </Badge>
          {cluster.reasons.map(r => <Badge key={r.code} tone="neutral">{r.message}</Badge>)}
        </div>
      </header>
      <div className="comparison-grid">
        <div className="col-headers">
          <div className="diff-label"></div>
          {visibleAlbums.map(album => {
            const isKeeper = currentKeeperId === album.folder_id;
            return (
              <div key={album.folder_id} className={`album-header ${isKeeper ? 'is-keeper' : ''}`} onClick={() => setFocusedAlbumId(album.folder_id)}>
                <div className="album-title-row">
                  <h4>{album.name}</h4>
                  {isKeeper && <Badge tone="success">נשמר</Badge>}
                </div>
                <p className="album-path">{album.path}</p>
                <div className="album-actions">
                  {!isKeeper && <Button variant="secondary" onClick={(e) => { e.stopPropagation(); handleDecision(cluster.cluster_id, album.folder_id); }}>בחר לשמירה</Button>}
                  <Button variant="ghost" onClick={(e) => { e.stopPropagation(); openExplorer(album.path); }}>פתח תיקייה</Button>
                  {!isKeeper && <Button variant="danger" onClick={(e) => { e.stopPropagation(); setSingleDeleteTarget({ clusterId: cluster.cluster_id, folderId: album.folder_id, name: album.name }); }}>מחק עכשיו</Button>}
                </div>
              </div>
            );
          })}
        </div>
        <div className="metrics-diff-section card">
          <h4 className="section-title">השוואת נתונים</h4>
          {METRICS.map(m => {
            const valA = albumA?.[m.key];
            const valB = albumB?.[m.key];
            const winnerId = metricWinners[m.key];
            const isWinnerA = winnerId ? winnerId === albumA?.folder_id : null;
            const isWinnerB = winnerId ? winnerId === albumB?.folder_id : null;
            return <VisualDiffRow key={m.key} label={m.label} valA={valA} valB={valB} type={m.type} isWinnerA={isWinnerA} isWinnerB={isWinnerB} />;
          })}
          <VisualDiffRow label="עטיפת אלבום" valA={albumA?.has_album_art ? "קיימת" : "חסרה"} valB={albumB?.has_album_art ? "קיימת" : "חסרה"} type="text" isWinnerA={albumA?.has_album_art && !albumB?.has_album_art} isWinnerB={albumB?.has_album_art && !albumA?.has_album_art} />
        </div>
        <div className="tracklist-diff-section card">
          <h4 className="section-title">רשימת שירים משולבת</h4>
          <div className="track-table">
            <div className="track-row track-header">
              <span>שיר</span>
              <span>אורך</span>
              {visibleAlbums.map(a => <span key={a.folder_id} className="text-center">{a.name}</span>)}
            </div>
            {trackRows.map(row => (
              <div key={row.key} className="track-row">
                <span className="track-name">{row.title}</span>
                <span className="track-duration">{formatMetricValue("duration", row.duration)}</span>
                {visibleAlbums.map(a => (
                  <span key={a.folder_id} className="text-center">
                    {row.presence[a.folder_id] ? <span className="icon-check">✓</span> : <span className="icon-missing">חסר</span>}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}