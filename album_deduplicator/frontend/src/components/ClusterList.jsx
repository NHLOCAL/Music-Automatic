import React from "react";
import { Card, Empty, Segmented, Space, Typography } from "antd";
import { Icon, StatusTag } from "./UI";
import {
  formatScore,
  getClusterDisplayTitle,
  getClusterSortPriority,
  getClusterStatusMeta,
  getRepresentativeClusterPair,
  hasClusterDecision,
} from "../utils";

const SEGMENT_OPTIONS = [
  { label: "בטוחים", value: "safe" },
  { label: "לסקירה", value: "review" },
  { label: "הכל", value: "all" },
];

export function ClusterList({
  clusters,
  selectedClusterId,
  setSelectedClusterId,
  decisions,
  selectedTab,
  setSelectedTab,
}) {
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
    <Card className="cluster-sidebar cartoon-panel" variant="borderless">
      <div className="cluster-sidebar-head">
        <Space align="center" size={8} style={{ marginBottom: 2 }}>
          <div className="soft-kicker" style={{ padding: "4px 8px", fontSize: "11px" }}>
            <Icon name="layers" size={12} />
            רשימת קבוצות
          </div>
        </Space>
        <Segmented
          block
          size="small"
          value={selectedTab}
          options={SEGMENT_OPTIONS}
          onChange={setSelectedTab}
        />
      </div>
      <div className="cluster-scroll" data-testid="cluster-scroll">
        {filteredClusters.length === 0 ? (
          <Empty
            className="desktop-empty"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="אין פריטים להצגה"
          />
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
              <Card
                key={cluster.cluster_id}
                className={`cluster-card cartoon-panel ${isActive ? "is-active" : ""}`}
                variant="borderless"
                onClick={() => setSelectedClusterId(cluster.cluster_id)}
              >
                <div className="cluster-card-headline">
                  <Typography.Text strong ellipsis={{ tooltip: getClusterDisplayTitle(cluster) }} style={{ flex: 1, minWidth: 0, fontSize: "12px" }}>
                    {getClusterDisplayTitle(cluster)}
                  </Typography.Text>
                  {!isActive && (
                    <StatusTag tone={statusMeta.tone} style={{ padding: "0 4px", minHeight: "18px", fontSize: "10px", border: "none" }}>
                      {statusMeta.label}
                    </StatusTag>
                  )}
                </div>
                <div className="cluster-card-meta">
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Icon name="music" size={10} /> {scoreLine}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Icon name="layers" size={10} /> {cluster.albums.filter((album) => !album.is_deleted).length} עותקים
                  </span>
                </div>
              </Card>
            );
          })
        )}
      </div>
    </Card>
  );
}