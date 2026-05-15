import React, { useEffect, useMemo, useState } from "react";
import { Button, Segmented, Tooltip } from "antd";
import { Icon, StatusTag } from "./UI";
import {
  getClusterDisplayTitle,
  getClusterStatusMeta,
  getVisibleAlbumCount,
  hasExplicitKeeperDecision,
  formatPercent,
  clusterMatchesReviewTab,
} from "../utils";

const SEGMENT_OPTIONS = [
  {
    label: <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="shield" size={13} />בטוחים</span>,
    value: "safe",
  },
  {
    label: <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="alert" size={13} />לסקירה</span>,
    value: "review",
  },
  {
    label: <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="check-circle" size={13} />הושלם</span>,
    value: "completed",
  },
];

function getReadinessRank(cluster, decisions) {
  const isResolved = hasExplicitKeeperDecision(cluster, decisions);
  const statusMeta = getClusterStatusMeta(cluster, isResolved);
  return statusMeta.tone === "success" ? 0 : 1;
}

export function ClusterList({ clusters, selectedClusterId, setSelectedClusterId, decisions, selectedTab, setSelectedTab }) {
  const [manualOrderIds, setManualOrderIds] = useState([]);
  const filteredClusters = useMemo(
    () => clusters.filter((cluster) => clusterMatchesReviewTab(cluster, selectedTab)),
    [clusters, selectedTab],
  );
  const displayedClusters = useMemo(() => {
    if (!manualOrderIds.length) return filteredClusters;
    const manualOrder = new Map(manualOrderIds.map((clusterId, index) => [clusterId, index]));
    return filteredClusters
      .map((cluster, index) => ({ cluster, index }))
      .sort((left, right) => {
        const leftOrder = manualOrder.get(left.cluster.cluster_id);
        const rightOrder = manualOrder.get(right.cluster.cluster_id);
        if (leftOrder !== undefined && rightOrder !== undefined) return leftOrder - rightOrder;
        if (leftOrder !== undefined) return -1;
        if (rightOrder !== undefined) return 1;
        return left.index - right.index;
      })
      .map(({ cluster }) => cluster);
  }, [filteredClusters, manualOrderIds]);

  useEffect(() => {
    setManualOrderIds([]);
  }, [selectedTab]);

  const sortByReadiness = () => {
    setManualOrderIds(
      filteredClusters
        .map((cluster, index) => ({ cluster, index }))
        .sort((left, right) => {
          const rankDiff = getReadinessRank(left.cluster, decisions) - getReadinessRank(right.cluster, decisions);
          return rankDiff || left.index - right.index;
        })
        .map(({ cluster }) => cluster.cluster_id),
    );
  };

  return (
    <div className="ide-sidebar">
      <div className="ide-sidebar-header">
        <Segmented
          block
          size="small"
          className="ide-sidebar-tabs"
          value={selectedTab}
          options={SEGMENT_OPTIONS}
          onChange={setSelectedTab}
        />
        <div className="ide-sidebar-tools">
          <Tooltip title="מיין לפי מוכנות">
            <Button
            size="small"
            className="ide-sidebar-sort-button"
            icon={<Icon name="sort" size={14} />}
            onClick={sortByReadiness}
            aria-label="מיין לפי מוכנות"
          >
            מוכנים תחילה
          </Button>
        </Tooltip>
      </div>
      </div>
      <div className="ide-sidebar-list" data-testid="cluster-scroll">
        {displayedClusters.map((cluster) => {
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
                <span>{getVisibleAlbumCount(cluster)} עותקים</span>
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
