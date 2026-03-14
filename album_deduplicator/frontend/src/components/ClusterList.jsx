import React from "react";
import { Segmented } from "antd";
import { Icon, StatusTag } from "./UI";
import {
  getClusterDisplayTitle,
  getClusterSortPriority,
  getClusterStatusMeta,
  hasExplicitKeeperDecision,
  formatPercent,
} from "../utils";

const SEGMENT_OPTIONS = [
  {
    label: <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="check-circle" size={13} />בטוחים</span>,
    value: "safe",
  },
  {
    label: <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="alert" size={13} />לסקירה</span>,
    value: "review",
  },
  {
    label: <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="layers" size={13} />הכל</span>,
    value: "all",
  },
];

export function ClusterList({ clusters, selectedClusterId, setSelectedClusterId, decisions, selectedTab, setSelectedTab }) {
  const filteredClusters = clusters
    .filter((cluster) => selectedTab === "all" || cluster.confidence_bucket === selectedTab)
    .sort((a, b) => getClusterSortPriority(a, decisions) - getClusterSortPriority(b, decisions));

  return (
    <div className="ide-sidebar">
      <div className="ide-sidebar-header">
        <Segmented block size="small" value={selectedTab} options={SEGMENT_OPTIONS} onChange={setSelectedTab} />
      </div>
      <div className="ide-sidebar-list" data-testid="cluster-scroll">
        {filteredClusters.map((cluster) => {
          const isActive = cluster.cluster_id === selectedClusterId;
          const isResolved = hasExplicitKeeperDecision(cluster, decisions);
          const statusMeta = getClusterStatusMeta(cluster, isResolved);
          const score = cluster.pairs?.[0] ? formatPercent(cluster.pairs[0].final_score) : "N/A";
          
          return (
            <div 
              key={cluster.cluster_id} 
              className={`ide-cluster-item ${isActive ? 'active' : ''}`}
              onClick={() => setSelectedClusterId(cluster.cluster_id)}
            >
              <div className="ide-cluster-title">
                {isResolved ? "✓ " : ""}{getClusterDisplayTitle(cluster)}
              </div>
              <div className="ide-cluster-meta">
                <span>{cluster.albums.filter(a => !a.is_deleted).length} עותקים</span>
                <span>התאמה: {score}</span>
              </div>
              <div className="ide-cluster-status">
                <StatusTag tone={statusMeta.tone}>{statusMeta.label}</StatusTag>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
