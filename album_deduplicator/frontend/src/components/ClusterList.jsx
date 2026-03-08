import React from "react";
import { Badge } from "./UI";
import {
  formatScore,
  getClusterDisplayTitle,
  getClusterSortPriority,
  getClusterStatusMeta,
  getRepresentativeClusterPair,
  hasClusterDecision,
} from "../utils";
export function ClusterList({ clusters, selectedClusterId, setSelectedClusterId, decisions, selectedTab, setSelectedTab }) {
  const filteredClusters = clusters
    .filter((cluster) => {
      if (selectedTab === "all") return true;
      return cluster.confidence_bucket === selectedTab;
    })
    .map((cluster, index) => ({ cluster, index }))
    .sort((left, right) => {
      const priorityDiff =
        getClusterSortPriority(left.cluster, decisions) - getClusterSortPriority(right.cluster, decisions);
      if (priorityDiff !== 0) return priorityDiff;
      return left.index - right.index;
    })
    .map(({ cluster }) => cluster);
  return (
    <div className="cluster-sidebar">
      <div className="sidebar-tabs">
        <div className="tab-group">
          <div className={`tab-item ${selectedTab === 'safe' ? 'active' : ''}`} onClick={() => setSelectedTab('safe')}>
            בטוחים
          </div>
          <div className={`tab-item ${selectedTab === 'review' ? 'active' : ''}`} onClick={() => setSelectedTab('review')}>
            לסקירה
          </div>
          <div className={`tab-item ${selectedTab === 'all' ? 'active' : ''}`} onClick={() => setSelectedTab('all')}>
            הכל
          </div>
        </div>
      </div>
      <div className="cluster-scroll">
        {filteredClusters.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            אין פריטים להצגה
          </div>
        ) : (
          filteredClusters.map((cluster) => {
            const isActive = cluster.cluster_id === selectedClusterId;
            const hasDecision = hasClusterDecision(decisions, cluster.cluster_id);
            const statusMeta = getClusterStatusMeta(cluster, hasDecision && decisions[cluster.cluster_id] !== null);
            const representativePair = getRepresentativeClusterPair(cluster, cluster.recommended_keeper_id);
            const scoreLine = representativePair
              ? representativePair.is_identical_by_hash
                ? "התאמה מלאה"
                : `התאמה: ${formatScore(representativePair.final_score)}`
              : "דורש בדיקה";
            return (
              <div
                key={cluster.cluster_id}
                className={`cluster-card ${isActive ? "active" : ""} ${statusMeta.label === "נבדק ומוכן" ? "status-ready" : ""}`}
                onClick={() => setSelectedClusterId(cluster.cluster_id)}
              >
                <div className="cluster-name" title={getClusterDisplayTitle(cluster)}>
                  {getClusterDisplayTitle(cluster)}
                </div>
                <div className="cluster-info">
                  <span className="cluster-scoreline">{scoreLine}</span>
                  {!isActive && <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}