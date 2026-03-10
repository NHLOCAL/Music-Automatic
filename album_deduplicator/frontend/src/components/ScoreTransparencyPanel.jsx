import React, { useMemo } from "react";
import { Card, Collapse, Typography } from "antd";

import { Icon } from "./UI";
import { formatPercent, getRepresentativeClusterPair } from "../utils";

export function ScoreTransparencyPanel({ cluster, currentKeeperId }) {
  const representativePair = useMemo(
    () => getRepresentativeClusterPair(cluster, currentKeeperId ?? cluster?.recommended_keeper_id ?? null),
    [cluster, currentKeeperId],
  );

  if (!cluster || !representativePair) return null;

  const aiInsightText = cluster.confidence_bucket === "safe"
    ? "רמת התאמה גבוהה. ההבדלים בין הקבצים מינוריים או לא קיימים כלל."
    : "התאמה גבולית. נמצא דמיון רב אך ייתכנו שינויים באיכות השמע או באורך הקבצים. נדרשת החלטה אנושית.";
  const geminiText = representativePair.gemini_reason || representativePair.gemini_verdict;
  const baseScore = representativePair.base_score ?? representativePair.final_score;
  const shouldShowBaseScore = Math.abs((baseScore ?? 0) - (representativePair.final_score ?? 0)) >= 0.05;

  const metrics = [
    {
      label: "ציון סופי",
      value: formatPercent(representativePair.final_score),
      icon: "sparkle",
    },
    {
      label: "השוואה מתמטית",
      value: formatPercent(representativePair.algorithmic_score),
      icon: "chart",
    },
    {
      label: "מודל AI",
      value: representativePair.is_identical_by_hash ? "Hash זהה" : formatPercent(representativePair.ml_score),
      icon: "database",
    },
  ];

  if (shouldShowBaseScore) {
    metrics.push({
      label: "Score בסיס",
      value: formatPercent(baseScore),
      icon: "compare",
    });
  }

  if (representativePair.gemini_score != null) {
    metrics.push({
      label: "חיזוק Gemini",
      value: formatPercent(representativePair.gemini_score),
      icon: "sparkle",
    });
  }

  return (
    <Collapse
      className="score-panel"
      variant="borderless"
      items={[
        {
          key: "transparency",
          label: (
            <div className="score-panel-header">
              <div className="score-panel-copy">
                <Typography.Text strong>איך המערכת הגיעה להחלטה</Typography.Text>
                <Typography.Text type="secondary">
                  פירוט score, הסבר אנושי, ושכבת השקיפות האלגוריתמית.
                </Typography.Text>
              </div>
              <Icon name="info" size={16} />
            </div>
          ),
          children: (
            <div>
              <Typography.Paragraph style={{ marginTop: 0 }}>
                {aiInsightText}
              </Typography.Paragraph>

              {geminiText ? (
                <Typography.Paragraph className="score-note">
                  <strong>הערת מודל שפה:</strong> {geminiText}
                </Typography.Paragraph>
              ) : null}

              <div className="score-metrics">
                {metrics.map((metric) => (
                  <Card key={metric.label} className="score-metric-card cartoon-panel" variant="borderless">
                    <Typography.Text type="secondary">
                      <Icon name={metric.icon} size={14} /> {metric.label}
                    </Typography.Text>
                    <Typography.Title level={4} style={{ margin: 0 }}>
                      {metric.value}
                    </Typography.Title>
                  </Card>
                ))}
              </div>
            </div>
          ),
        },
      ]}
    />
  );
}
