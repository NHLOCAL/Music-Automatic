import React, { useMemo } from "react";
import { Button, Tooltip } from "antd";
import { Icon } from "./UI";
import { ScoreTransparencyPanel } from "./ScoreTransparencyPanel";
import { buildTrackComparisonRows, formatBitrate, formatDuration, formatSizeMb, getTrackRowTone } from "../utils";

export function DiffWorkspace({ cluster, currentKeeperId, handleDecision, openExplorer, previewCount, onOpenFinalize, onExecuteMassDelete, isExecuting }) {
  if (!cluster) {
    return <div className="ide-main" style={{alignItems:'center', justifyContent:'center', color:'#888'}}>בחר קבוצה מהרשימה</div>;
  }

  const visibleAlbums = useMemo(() => cluster.albums.filter((a) => !a.is_deleted), [cluster]);
  const trackRows = useMemo(() => buildTrackComparisonRows(visibleAlbums), [visibleAlbums]);
  const visibleAlbumIds = visibleAlbums.map(a => a.folder_id);

  return (
    <div className="ide-main">
      <div className="ide-toolbar">
        <div style={{display:'flex', gap: 12, alignItems:'center'}}>
          <span className={`badge ${cluster.confidence_bucket === 'safe' ? 'success' : 'warning'}`}>
            {cluster.confidence_bucket === 'safe' ? 'בטוח' : 'לסקירה'}
          </span>
          <span style={{fontSize: 12, fontWeight: 600}}>{cluster.human_summary}</span>
          <ScoreTransparencyPanel cluster={cluster} currentKeeperId={currentKeeperId} />
        </div>
        <div style={{display:'flex', gap: 8}}>
          {previewCount > 0 && (
            <>
              <Button size="small" onClick={onOpenFinalize}>תצוגה מקדימה ({previewCount})</Button>
              <Button size="small" type="primary" danger loading={isExecuting} onClick={onExecuteMassDelete}>
                העבר למחזור ({previewCount})
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="ide-diff-container">
        {visibleAlbums.map((album, idx) => {
          const isKeeper = currentKeeperId === album.folder_id;
          const isTrash = Boolean(currentKeeperId) && !isKeeper;
          const isRec = cluster.recommended_keeper_id === album.folder_id;

          return (
            <div key={album.folder_id} className={`ide-pane ${isKeeper ? 'is-keeper' : isTrash ? 'is-trash' : ''}`}>
              <div className="ide-pane-header">
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                  <strong style={{fontSize: 13}}>עותק {idx + 1} {isRec && <span style={{color: '#0060df', fontSize:11}}>★ מומלץ</span>}</strong>
                  <Tooltip title="פתח בתיקייה"><Icon name="folder" size={14} style={{cursor:'pointer'}} onClick={() => openExplorer(album.path)}/></Tooltip>
                </div>
                <div className="ide-pane-path" title={album.path}>{album.path}</div>
                <div className="ide-pane-metrics">
                  <span>ביטרייט: <strong>{formatBitrate(album.avg_bitrate)}</strong></span>
                  <span>גודל: <strong>{formatSizeMb(album.total_size_mb)}</strong></span>
                  <span>איכות: <strong>{album.quality_score ? `${album.quality_score.toFixed(1)}/100` : '-'}</strong></span>
                </div>
              </div>
              
              <div className="ide-pane-body">
                {trackRows.map(row => {
                  const entry = row.entries[album.folder_id];
                  const tone = getTrackRowTone(row, visibleAlbumIds);
                  const isDiff = tone === 'different';
                  
                  if (!entry) return <div key={row.key} className="ide-track-row diff-err">חסר בעותק זה</div>;
                  
                  return (
                    <div key={row.key} className={`ide-track-row ${isDiff ? 'diff-warn' : ''}`}>
                      <span style={{whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis'}} title={entry.filename}>{entry.filename}</span>
                      <span style={{color:'#666', flexShrink:0}}>{formatDuration(entry.duration)}</span>
                    </div>
                  );
                })}
              </div>

              <div className="ide-pane-footer">
                <Button 
                  type={isKeeper ? "primary" : "default"} 
                  danger={isTrash}
                  style={{width: '100%'}}
                  onClick={() => handleDecision(cluster.cluster_id, album.folder_id)}
                >
                  {isKeeper ? "נבחר לשמירה (Keeper)" : isTrash ? "יסומן למחיקה (Trash)" : "שמור עותק זה"}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}