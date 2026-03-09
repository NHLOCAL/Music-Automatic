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
    <Card className="cluster-sidebar cartoon-card" variant="borderless">
      <div className="cluster-sidebar-head">
        <Space align="center" size={12}>
          <div className="soft-kicker">
            <Icon name="layers" size={14} />
            מרכז סקירה
          </div>
          <StatusTag tone="primary" icon="layers">
            {filteredClusters.length}
          </StatusTag>
        </Space>
        <Typography.Title level={3} style={{ margin: 0 }}>
          קבוצות אלבומים
        </Typography.Title>
        <Typography.Paragraph className="muted-copy" style={{ margin: 0 }}>
          בחר קבוצה אחת, השווה בין העותקים, והחלט איזה עותק נשאר.
        </Typography.Paragraph>
      </div>

      <Segmented
        block
        size="large"
        value={selectedTab}
        options={SEGMENT_OPTIONS}
        onChange={setSelectedTab}
      />

      <div className="cluster-scroll">
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
                  <Typography.Text strong>{getClusterDisplayTitle(cluster)}</Typography.Text>
                  {!isActive && (
                    <StatusTag tone={statusMeta.tone} icon={statusMeta.tone === "success" ? "check" : "alert"}>
                      {statusMeta.label}
                    </StatusTag>
                  )}
                </div>

                <Space orientation="vertical" size={10} style={{ width: "100%" }}>
                  <Typography.Text className="muted-copy">
                    <Icon name="music" size={12} /> {scoreLine}
                  </Typography.Text>

                  <div className="cluster-card-meta">
                    <span>
                      <Icon name="layers" size={12} /> {cluster.albums.filter((album) => !album.is_deleted).length} עותקים
                    </span>
                    <span>
                      <Icon name="folder" size={12} /> {cluster.confidence_bucket === "safe" ? "מוכן לפעולה" : "דורש החלטה"}
                    </span>
                  </div>
                </Space>
              </Card>
            );
          })
        )}
      </div>
    </Card>
  );
}
