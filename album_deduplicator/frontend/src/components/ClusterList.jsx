import React from "react";
import { Badge } from "./UI";

export function ClusterList({
  clusters,
  selectedClusterId,
  setSelectedClusterId,
  decisions,
}) {
  if (!clusters.length) {
    return (
      <div className="empty-state">
        <p>אין תוצאות להצגה בקטגוריה זו.</p>
      </div>
    );
  }

  return (
    <div className="cluster-sidebar">
      {clusters.map((cluster) => {
        const isActive = cluster.cluster_id === selectedClusterId;
        const currentKeeperId = decisions[cluster.cluster_id] ?? (cluster.resolution_state === "auto" ? cluster.recommended_keeper_id : null);
        const albums = cluster.albums.filter((album) => !album.is_deleted);
        const isSafe = cluster.confidence_bucket === "safe";

        return (
          <div
            key={cluster.cluster_id}
            className={`cluster-item ${isActive ? "active" : ""}`}
            onClick={() => setSelectedClusterId(cluster.cluster_id)}
          >
            <div className="cluster-item-head">
              <Badge tone={isSafe ? "success" : "warning"}>
                {isSafe ? "בטוח" : "סקירה"}
              </Badge>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-soft)' }}>
                {albums.length} עותקים
              </span>
            </div>
            <div className="cluster-item-title" title={cluster.human_summary}>
              {cluster.human_summary.split('.')[0]}
            </div>
            <div className="cluster-item-meta" style={{ marginTop: '8px' }}>
              {currentKeeperId ? (
                <span style={{ color: 'var(--success)', fontWeight: 600 }}>נבחר שומר</span>
              ) : (
                <span style={{ color: 'var(--warning)' }}>ממתין להחלטה</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}