import React from "react";
import { Badge } from "./UI";
export function ClusterList({ clusters, selectedClusterId, setSelectedClusterId, decisions, handleDecision }) {
  if (!clusters.length) {
    return <div className="empty-list">אין תוצאות להצגה בקטגוריה זו.</div>;
  }
  return (
    <div className="cluster-list">
      {clusters.map((cluster) => {
        const isActive = cluster.cluster_id === selectedClusterId;
        const currentKeeperId = decisions[cluster.cluster_id] ?? (cluster.resolution_state === "auto" ? cluster.recommended_keeper_id : null);
        const albums = cluster.albums.filter(a => !a.is_deleted);
        return (
          <div key={cluster.cluster_id} className={`cluster-card card ${isActive ? "active" : ""}`} onClick={() => setSelectedClusterId(cluster.cluster_id)}>
            <div className="cluster-card-header">
              <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
                {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
              </Badge>
              {cluster.comparison_highlights.slice(0, 1).map(h => (
                <span key={h.id} className="highlight-text">{h.label}</span>
              ))}
            </div>
            <h3 className="cluster-title">{albums.map(a => a.name).join(" / ")}</h3>
            <div className="cluster-actions">
              {albums.map(album => {
                const isSelected = currentKeeperId === album.folder_id;
                return (
                  <button key={album.folder_id} className={`choice-btn ${isSelected ? "selected" : ""}`} onClick={(e) => { e.stopPropagation(); handleDecision(cluster.cluster_id, album.folder_id); }}>
                    {album.name}
                  </button>
                );
              })}
              <button className={`choice-btn ${!currentKeeperId ? "selected" : ""}`} onClick={(e) => { e.stopPropagation(); handleDecision(cluster.cluster_id, null); }}>
                דלג
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}