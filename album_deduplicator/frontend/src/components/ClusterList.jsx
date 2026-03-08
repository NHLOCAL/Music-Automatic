import React from "react";
import { Badge, Icon } from "./UI";
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
      <div className="cluster-sidebar-top">
        <div className="cluster-sidebar-title">
          <div>
            <span className="sidebar-kicker">מרכז סקירה</span>
            <h3>קבוצות אלבומים</h3>
          </div>
          <Badge tone="neutral" icon="layers">{filteredClusters.length}</Badge>
        </div>
        <p>בחר קבוצה אחת, השווה בין העותקים, והחלט איזה עותק נשאר.</p>
      </div>
      <div className="sidebar-tabs">
        <div className="tab-group">
          <div className={`tab-item ${selectedTab === 'safe' ? 'active' : ''}`} onClick={() => setSelectedTab('safe')}>
            <Icon name="shield" size={16} /> בטוחים
          </div>
          <div className={`tab-item ${selectedTab === 'review' ? 'active' : ''}`} onClick={() => setSelectedTab('review')}>
            <Icon name="alert" size={16} /> לסקירה
          </div>
          <div className={`tab-item ${selectedTab === 'all' ? 'active' : ''}`} onClick={() => setSelectedTab('all')}>
            <Icon name="folder" size={16} /> הכל
          </div>
        </div>
      </div>
      
      <div className="cluster-scroll">
        {filteredClusters.length === 0 ? (
          <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--text-tertiary)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
            <Icon name="check-circle" size={32} />
            <span>אין פריטים להצגה</span>
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

            const bucketIcon = cluster.confidence_bucket === "safe" ? "shield" : "alert";

            return (
              <div
                key={cluster.cluster_id}
                className={`cluster-card ${isActive ? "active" : ""} ${statusMeta.label === "נבדק ומוכן" ? "status-ready" : ""}`}
                onClick={() => setSelectedClusterId(cluster.cluster_id)}
              >
                <div className="cluster-header">
                  <div className="cluster-name" title={getClusterDisplayTitle(cluster)}>
                    {getClusterDisplayTitle(cluster)}
                  </div>
                  {!isActive && <Icon name={statusMeta.label === "נבדק ומוכן" ? "check" : bucketIcon} size={14} className={`tone-${statusMeta.tone}`} />}
                </div>
                
                <div className="cluster-info">
                  <span className="cluster-scoreline">
                    <Icon name="music" size={12} />
                    {scoreLine}
                  </span>
                  {!isActive && <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>}
                </div>
                <div className="cluster-meta">
                  <span>
                    <Icon name="layers" size={12} />
                    {cluster.albums.filter((album) => !album.is_deleted).length} עותקים
                  </span>
                  <span>
                    <Icon name="folder" size={12} />
                    {cluster.confidence_bucket === "safe" ? "מוכן לפעולה" : "דורש החלטה"}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
