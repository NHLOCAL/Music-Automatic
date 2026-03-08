import React, { useMemo } from "react";
import { formatPercent, getRepresentativeClusterPair } from "../utils";

export function ScoreTransparencyPanel({ cluster, currentKeeperId }) {
  const visibleAlbums = useMemo(
    () => (Array.isArray(cluster?.albums) ? cluster.albums.filter((album) => !album.is_deleted) : []),
    [cluster]
  );

  const representativePair = useMemo(
    () => getRepresentativeClusterPair(cluster, currentKeeperId ?? cluster?.recommended_keeper_id ?? null),
    [cluster, currentKeeperId]
  );

  if (!cluster || !representativePair) return null;

  const aiInsightText = cluster.confidence_bucket === "safe"
    ? `המערכת זיהתה התאמה גבוהה מאוד בין העותקים וקובעת בביטחון שאפשר למחוק כפילויות. ההבדלים מינוריים או לא קיימים.`
    : `המערכת מזהה דמיון רב, אך נדרשת החלטה אנושית. ייתכנו שינויים באיכות השמע, באורך השירים, או שהנתונים גבוליים להכרעה אוטומטית.`;

  const geminiText = representativePair.gemini_reason || representativePair.gemini_verdict;

  return (
    <div className="ai-panel">
      <div className="ai-header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
        </svg>
        תובנות ניתוח חכם
      </div>
      
      <div className="ai-insight">
        {aiInsightText}
        {geminiText && (
          <div style={{ marginTop: '8px', color: 'var(--color-warning-text)', fontSize: '0.85rem' }}>
            <strong>הערת מודל שפה:</strong> {geminiText}
          </div>
        )}
      </div>

      <div className="ai-details-grid">
        <div className="ai-metric">
          <span className="ai-metric-label">ציון סופי משוקלל</span>
          <span className="ai-metric-val">{formatPercent(representativePair.final_score)}</span>
        </div>
        <div className="ai-metric">
          <span className="ai-metric-label">השוואה מתמטית (Base)</span>
          <span className="ai-metric-val">{formatPercent(representativePair.algorithmic_score)}</span>
        </div>
        <div className="ai-metric">
          <span className="ai-metric-label">למידת מכונה (ML)</span>
          <span className="ai-metric-val">
            {representativePair.is_identical_by_hash 
              ? "Hash זהה" 
              : formatPercent(representativePair.ml_score)}
          </span>
        </div>
      </div>
    </div>
  );
}