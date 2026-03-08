import React, { useMemo } from "react";
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
  return (
    <details className="ai-panel-details">
      <summary className="ai-panel-summary">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
        מידע מערכת וניתוח אלגוריתמי
      </summary>
      <div className="ai-panel-content">
        <div className="ai-insight-text">
          {aiInsightText}
          {geminiText && (
            <div style={{ marginTop: '8px', color: 'var(--color-warning-text)' }}>
              <strong>הערת מודל שפה:</strong> {geminiText}
            </div>
          )}
        </div>
        <div className="ai-metrics-row">
          <div className="ai-metric-item">
            <span className="label">ציון סופי משוקלל</span>
            <span className="val">{formatPercent(representativePair.final_score)}</span>
          </div>
          <div className="ai-metric-item">
            <span className="label">השוואה מתמטית</span>
            <span className="val">{formatPercent(representativePair.algorithmic_score)}</span>
          </div>
          <div className="ai-metric-item">
            <span className="label">למידת מכונה</span>
            <span className="val">
              {representativePair.is_identical_by_hash
                ? "Hash זהה"
                : formatPercent(representativePair.ml_score)}
            </span>
          </div>
        </div>
      </div>
    </details>
  );
}