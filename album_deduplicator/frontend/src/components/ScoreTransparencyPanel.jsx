import React, { useMemo, useState } from "react";

import { Badge, Button } from "./UI";
import {
  formatPercent,
  getPairAlbumsLabel,
  getRepresentativeClusterPair,
} from "../utils";

function ScoreMetricCard({ label, value, hint = null, tone = "neutral", emphasize = false }) {
  return (
    <div className={`score-metric-card tone-${tone} ${emphasize ? "is-emphasized" : ""}`}>
      <div className="score-metric-label">{label}</div>
      <div className="score-metric-value">{value}</div>
      {hint ? <div className="score-metric-hint">{hint}</div> : null}
    </div>
  );
}

function renderScoreValue(value, unavailableLabel) {
  if (value === null || value === undefined) return unavailableLabel;
  return formatPercent(value);
}

export function ScoreTransparencyPanel({ cluster, currentKeeperId }) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const visibleAlbums = useMemo(
    () => (Array.isArray(cluster?.albums) ? cluster.albums.filter((album) => !album.is_deleted) : []),
    [cluster],
  );

  const representativePair = useMemo(
    () => getRepresentativeClusterPair(cluster, currentKeeperId ?? cluster?.recommended_keeper_id ?? null),
    [cluster, currentKeeperId],
  );

  if (!cluster) return null;

  const keeper = visibleAlbums.find((album) => album.folder_id === (currentKeeperId ?? cluster.recommended_keeper_id)) ?? null;
  const reasons = Array.isArray(cluster.reasons) ? cluster.reasons : [];
  const highlights = Array.isArray(cluster.comparison_highlights) ? cluster.comparison_highlights : [];
  const pairs = Array.isArray(cluster.pairs) ? cluster.pairs : [];
  const pairScopeLabel = representativePair
    ? getPairAlbumsLabel(representativePair, visibleAlbums)
    : keeper
      ? `העותק שנשמר כרגע: ${keeper.name}`
      : "אין כרגע pair זמין להצגה";

  const explanation = representativePair
    ? cluster.confidence_bucket === "safe"
      ? `המערכת מדרגת את ${pairScopeLabel} כעותקים בטוחים למחיקה לפי הציון הסופי, ואז בוחרת איזה עותק עדיף לשמור.`
      : `המערכת מדרגת את ${pairScopeLabel} כדומים מאוד, אבל עדיין משאירה את ההחלטה בידיים שלך כי הציון לא מספיק חד-משמעי.`
    : cluster.human_summary;

  return (
    <section className="score-transparency-panel">
      <div className="score-transparency-head">
        <div>
          <div className="score-eyebrow">שקיפות תוצאה</div>
          <h3>איך המערכת הגיעה להחלטה</h3>
          <p>{explanation}</p>
        </div>
        <Button
          variant={showAdvanced ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setShowAdvanced((current) => !current)}
        >
          {showAdvanced ? "הסתר פרטים מתקדמים" : "הצג פרטים מתקדמים"}
        </Button>
      </div>

      <div className="score-context-row">
        <div className="score-context-copy">
          <strong>{pairScopeLabel}</strong>
          <span>
            {keeper
              ? `העותק שנבחר כרגע לשמירה הוא "${keeper.name}".`
              : "עדיין לא נבחר עותק לשמירה, לכן מוצג הפירוק הרלוונטי ביותר שקיים כרגע."}
          </span>
        </div>
        <div className="score-context-badges">
          <Badge tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}>
            {cluster.confidence_bucket === "safe" ? "בטוח למחיקה" : "דורש סקירה"}
          </Badge>
          {representativePair?.is_identical_by_hash ? <Badge tone="success">Hash זהה</Badge> : null}
          {cluster.recommended_keeper_reason ? <Badge tone="neutral">{cluster.recommended_keeper_reason}</Badge> : null}
        </div>
      </div>

      <div className="score-metrics-grid">
        <ScoreMetricCard
          label="המודל המתמטי"
          value={renderScoreValue(representativePair?.algorithmic_score, "ללא נתון")}
          hint="חישוב דמיון מבוסס metadata, קבצים ואיכות"
        />
        <ScoreMetricCard
          label="ציון ה-AI המקומי"
          value={renderScoreValue(representativePair?.ml_score, representativePair?.is_identical_by_hash ? "לא נדרש" : "לא זמין")}
          hint={representativePair?.is_identical_by_hash ? "דולג כי ה-hash כבר הוכיח זהות" : "מודל ML מקומי שמשווה את שני האלבומים"}
        />
        <ScoreMetricCard
          label="ציון משולב"
          value={renderScoreValue(representativePair?.base_score, "ללא נתון")}
          hint="45% מתמטי + 55% AI מקומי"
          tone="warning"
        />
        <ScoreMetricCard
          label="Gemini"
          value={renderScoreValue(representativePair?.gemini_score, "לא הופעל")}
          hint="רץ רק על זוגות גבוליים"
        />
        <ScoreMetricCard
          label="הציון הסופי"
          value={renderScoreValue(representativePair?.final_score, "ללא נתון")}
          hint="זה הציון שקובע safe לעומת review"
          tone={cluster.confidence_bucket === "safe" ? "success" : "warning"}
          emphasize
        />
      </div>

      {(highlights.length > 0 || reasons.length > 0) && (
        <div className="score-support-grid">
          {highlights.length > 0 && (
            <div className="score-support-card">
              <div className="score-support-title">מה בלט בהשוואה</div>
              <div className="score-pill-list">
                {highlights.map((item) => (
                  <span key={item.id} className={`score-pill tone-${item.tone}`}>
                    {item.label}
                    {item.value ? ` • ${item.value}` : ""}
                  </span>
                ))}
              </div>
            </div>
          )}
          {reasons.length > 0 && (
            <div className="score-support-card">
              <div className="score-support-title">למה הוצע לשמור דווקא את העותק הזה</div>
              <div className="score-reason-list">
                {reasons.map((reason) => (
                  <div key={`${reason.code}-${reason.message}`} className="score-reason-item">
                    <span className="score-reason-dot" />
                    <span>{reason.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {showAdvanced && (
        <div className="score-advanced-panel">
          <div className="score-advanced-section">
            <div className="score-advanced-title">תקציר טכני</div>
            <p>{cluster.technical_summary || "אין כרגע תקציר טכני נוסף לקבוצה זו."}</p>
          </div>

          {pairs.length > 0 && (
            <div className="score-advanced-section">
              <div className="score-advanced-title">פירוט מלא לכל pair</div>
              <div className="score-pair-table">
                <div className="score-pair-row is-head">
                  <span>Pair</span>
                  <span>מתמטי</span>
                  <span>AI</span>
                  <span>משולב</span>
                  <span>Gemini</span>
                  <span>סופי</span>
                </div>
                {pairs.map((pair) => (
                  <div key={pair.pair_id} className="score-pair-row">
                    <span className="score-pair-name">{getPairAlbumsLabel(pair, visibleAlbums)}</span>
                    <span>{renderScoreValue(pair.algorithmic_score, "ללא נתון")}</span>
                    <span>{renderScoreValue(pair.ml_score, pair.is_identical_by_hash ? "לא נדרש" : "לא זמין")}</span>
                    <span>{renderScoreValue(pair.base_score, "ללא נתון")}</span>
                    <span>{renderScoreValue(pair.gemini_score, "לא הופעל")}</span>
                    <span className="score-pair-final">{renderScoreValue(pair.final_score, "ללא נתון")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(cluster.reason_codes?.length > 0 || representativePair?.reason_codes?.length > 0 || representativePair?.gemini_reason || representativePair?.gemini_error || representativePair?.gemini_verdict) && (
            <div className="score-advanced-section">
              <div className="score-advanced-title">Signals נוספים למשתמש מתקדם</div>
              <div className="score-advanced-meta">
                {cluster.reason_codes?.length > 0 ? (
                  <div>
                    <strong>Reason codes של הקבוצה:</strong> {cluster.reason_codes.join(", ")}
                  </div>
                ) : null}
                {representativePair?.reason_codes?.length > 0 ? (
                  <div>
                    <strong>Reason codes של ה-pair:</strong> {representativePair.reason_codes.join(", ")}
                  </div>
                ) : null}
                {representativePair?.gemini_verdict ? (
                  <div>
                    <strong>Gemini verdict:</strong> {representativePair.gemini_verdict}
                  </div>
                ) : null}
                {representativePair?.gemini_reason ? (
                  <div>
                    <strong>Gemini reason:</strong> {representativePair.gemini_reason}
                  </div>
                ) : null}
                {representativePair?.gemini_error ? (
                  <div>
                    <strong>Gemini error:</strong> {representativePair.gemini_error}
                  </div>
                ) : null}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
