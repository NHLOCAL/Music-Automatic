import React from "react";
import { Badge } from "./UI";

export function ClusterList({ clusters, selectedClusterId, setSelectedClusterId, decisions, selectedTab, setSelectedTab }) {
  
  const filteredClusters = clusters.filter(c => {
    if (selectedTab === 'all') return true;
    return c.confidence_bucket === selectedTab;
  });

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="segmented-control">
          <div className={`segment ${selectedTab === 'safe' ? 'active' : ''}`} onClick={() => setSelectedTab('safe')}>
            בטוח
          </div>
          <div className={`segment ${selectedTab === 'review' ? 'active' : ''}`} onClick={() => setSelectedTab('review')}>
            לסקירה
          </div>
          <div className={`segment ${selectedTab === 'all' ? 'active' : ''}`} onClick={() => setSelectedTab('all')}>
            הכל
          </div>
        </div>
      </div>
      <div className="cluster-list">
        {filteredClusters.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>
            אין קבוצות להצגה בקטגוריה זו.
          </div>
        ) : (
          filteredClusters.map((cluster) => {
            const isActive = cluster.cluster_id === selectedClusterId;
            const currentKeeperId = decisions[cluster.cluster_id] ?? (cluster.resolution_state === "auto" ? cluster.recommended_keeper_id : null);
            const albums = cluster.albums.filter((a) => !a.is_deleted);
            const isSafe = cluster.confidence_bucket === "safe";

            return (
              <div key={cluster.cluster_id} className={`cluster-item ${isActive ? "active" : ""}`} onClick={() => setSelectedClusterId(cluster.cluster_id)}>
                <div className="cluster-item-header">
                  <div className="cluster-title">{cluster.human_summary.split('.')[0]}</div>
                </div>
                <div className="cluster-meta">
                  <span className="text-secondary">{albums.length} עותקים</span>
                  {currentKeeperId ? (
                    <Badge tone={isActive ? "neutral" : "success"}>טופל</Badge>
                  ) : (
                    <Badge tone={isActive ? "neutral" : "warning"}>ממתין</Badge>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}