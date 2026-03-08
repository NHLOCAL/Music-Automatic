import React from "react";
import { Badge } from "./UI";
import { getClusterDisplayTitle, getClusterListSubtitle, getClusterStatusMeta, hasClusterDecision } from "../utils";

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
            בטוחים
          </div>
          <div className={`segment ${selectedTab === 'review' ? 'active' : ''}`} onClick={() => setSelectedTab('review')}>
            לסקירה
          </div>
          <div className={`segment ${selectedTab === 'all' ? 'active' : ''}`} onClick={() => setSelectedTab('all')}>
            כולם
          </div>
        </div>
      </div>
      <div className="cluster-list">
        {filteredClusters.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            אין אלבומים בקטגוריה זו.
          </div>
        ) : (
          filteredClusters.map((cluster) => {
            const isActive = cluster.cluster_id === selectedClusterId;
            const hasDecision = hasClusterDecision(decisions, cluster.cluster_id);
            const statusMeta = getClusterStatusMeta(cluster, hasDecision && decisions[cluster.cluster_id] !== null);
            
            return (
              <div key={cluster.cluster_id} className={`cluster-item ${isActive ? "active" : ""}`} onClick={() => setSelectedClusterId(cluster.cluster_id)}>
                <div className="cluster-title" title={getClusterDisplayTitle(cluster)}>
                  {getClusterDisplayTitle(cluster)}
                </div>
                <div className="cluster-subtitle" title={cluster.human_summary}>
                  {getClusterListSubtitle(cluster)}
                </div>
                <div className="cluster-meta">
                  <Badge tone={isActive ? "neutral" : statusMeta.tone}>{statusMeta.label}</Badge>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}