import React from "react";
import { Popover } from "antd";
import { Icon } from "./UI";
import { formatPercent, getPairAlbumsLabel, getRepresentativeClusterPair } from "../utils";

function formatGeminiVerdict(verdict) {
  if (verdict === "duplicate") return "כפילות";
  if (verdict === "different") return "שונה";
  if (verdict === "uncertain") return "לא ודאי";
  return "לא התקבלה הכרעה";
}

function getPairForDisplay(cluster, currentKeeperId) {
  return getRepresentativeClusterPair(cluster, currentKeeperId ?? cluster?.recommended_keeper_id);
}

export function ScoreDetails({ cluster, currentKeeperId, compact = false }) {
  const pair = getPairForDisplay(cluster, currentKeeperId);
  if (!pair) {
    return (
      <div className="score-details-empty">
        אין פירוט ציונים זמין לקבוצה הזו.
      </div>
    );
  }

  const pairLabel = getPairAlbumsLabel(pair, cluster?.albums ?? []);
  const hasGeminiResult = pair.gemini_score !== null
    && pair.gemini_score !== undefined
    && !pair.gemini_error;
  const geminiReason = pair.gemini_reason || pair.gemini_error || "לא התקבל נימוק מג'מיני עבור זוג זה.";

  return (
    <div className={`score-details ${compact ? "score-details--compact" : ""}`}>
      <div className="score-details-header">
        <div>
          <div className="score-details-title">פירוט התאמה</div>
          <div className="score-details-pair" title={pairLabel}>{pairLabel}</div>
        </div>
        <div className="score-details-final" aria-label={`ציון סופי ${formatPercent(pair.final_score)}`}>
          {formatPercent(pair.final_score)}
        </div>
      </div>

      <div className="score-details-grid">
        <div className="score-detail-metric">
          <span>אלגוריתם</span>
          <strong>{formatPercent(pair.algorithmic_score)}</strong>
        </div>
        <div className="score-detail-metric">
          <span>ML</span>
          <strong>{pair.is_identical_by_hash ? "Hash זהה" : formatPercent(pair.ml_score)}</strong>
        </div>
        <div className="score-detail-metric">
          <span>בסיס לפני AI</span>
          <strong>{formatPercent(pair.base_score)}</strong>
        </div>
        <div className="score-detail-metric">
          <span>Gemini</span>
          <strong>{hasGeminiResult ? formatPercent(pair.gemini_score) : "לא הופעל"}</strong>
        </div>
      </div>

      <div className={`score-details-gemini ${pair.gemini_error ? "is-error" : ""}`}>
        <div className="score-details-gemini-head">
          <span>הכרעת Gemini</span>
          <strong>{formatGeminiVerdict(pair.gemini_verdict)}</strong>
        </div>
        <p>{geminiReason}</p>
      </div>
    </div>
  );
}

export function ScoreInfoButton({ cluster, currentKeeperId, label = "פירוט ציונים", placement = "bottomRight" }) {
  return (
    <Popover
      content={<ScoreDetails cluster={cluster} currentKeeperId={currentKeeperId} compact />}
      title="ציונים ונימוק"
      placement={placement}
      trigger={["click"]}
    >
      <button
        type="button"
        className="score-info-button"
        aria-label={label}
        title={label}
        onClick={(event) => event.stopPropagation()}
      >
        <Icon name="info" size={14} />
      </button>
    </Popover>
  );
}

export function ScoreTransparencyPanel({ cluster, currentKeeperId }) {
  const pair = getPairForDisplay(cluster, currentKeeperId);
  if (!pair) return null;

  return (
    <Popover
      content={<ScoreDetails cluster={cluster} currentKeeperId={currentKeeperId} compact />}
      title="ציונים ונימוק"
      placement="bottomRight"
      trigger={["click"]}
    >
      <div className="ide-transparency-inline" style={{cursor: 'pointer'}}>
        <Icon name="info" size={14} /> נתוני השוואה
      </div>
    </Popover>
  );
}
