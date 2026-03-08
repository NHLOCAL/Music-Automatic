import React, { useMemo } from "react";
import { Icon } from "./UI";
import { formatPercent, getRepresentativeClusterPair } from "../utils";
export function ScoreTransparencyPanel({ cluster, currentKeeperId }) {
  const representativePair = useMemo(
    () => getRepresentativeClusterPair(cluster, currentKeeperId ?? cluster?.recommended_keeper_id ?? null),
    [cluster, currentKeeperId]
  );
  if (!cluster || !representativePair) return null;
  const aiInsightText = cluster.confidence_bucket === "safe"
    ? `רמת התאמה גבוהה. ההבדלים בין הקבצים מינוריים או לא קיימים כלל.`
    : `התאמה גבולית. נמצא דמיון רב אך ייתכנו שינויים באיכות השמע או באורך הקבצים. נדרשת החלטה אנושית.`;
  const geminiText = representativePair.gemini_reason || representativePair.gemini_verdict;
  const metrics = [
    {
      label: "ציון סופי",
      value: formatPercent(representativePair.final_score),
      icon: "sparkle",
      tone: "primary",
    },
    {
      label: "השוואה מתמטית",
      value: formatPercent(representativePair.algorithmic_score),
      icon: "chart",
      tone: "neutral",
    },
    {
      label: "למידת מכונה",
      value: representativePair.is_identical_by_hash ? "Hash זהה" : formatPercent(representativePair.ml_score),
      icon: "database",
      tone: "success",
    },
    {
      label: "Score בסיס",
      value: formatPercent(representativePair.base_score ?? representativePair.final_score),
      icon: "compare",
      tone: "warning",
    },
  ];
  if (representativePair.gemini_score != null) {
    metrics.push({
      label: "חיזוק Gemini",
      value: formatPercent(representativePair.gemini_score),
      icon: "sparkle",
      tone: "warning",
    });
  }
  return (
    <details className="ai-panel-details">
      <summary className="ai-panel-summary">
        <div className="ai-panel-summary-main">
          <Icon name="info" size={14} />
          <div>
            <strong>איך המערכת הגיעה להחלטה</strong>
            <span>פירוט score, הסבר אנושי, ושכבת השקיפות האלגוריתמית.</span>
          </div>
        </div>
        <Icon name="chevron-down" size={16} className="ai-panel-chevron" />
      </summary>
      <div className="ai-panel-content">
        <div className="ai-insight-text">
          {aiInsightText}
          {geminiText && (
            <div className="ai-panel-note">
              <strong>הערת מודל שפה:</strong> {geminiText}
            </div>
          )}
        </div>
        <div className="ai-metrics-row">
          {metrics.map((metric) => (
            <div key={metric.label} className={`ai-metric-item tone-${metric.tone}`}>
              <span className="ai-metric-icon">
                <Icon name={metric.icon} size={14} />
              </span>
              <span className="label">{metric.label}</span>
              <span className="val">{metric.value}</span>
            </div>
          ))}
        </div>
      </div>
    </details>
  );
}
