import React, { useMemo, useState } from "react";
import { Button } from "./UI";

const SCAN_STEPS = [
  { id: "queued", label: "מוכן" },
  { id: "setup", label: "הכנה" },
  { id: "scan", label: "סריקה" },
  { id: "compare", label: "השוואה" },
  { id: "complete", label: "תוצאות" },
];

function getFolderLabel(index) {
  if (index === 0) return "ספריית מקור";
  if (index === 1) return "ספריית ארכיון";
  return `Root נוסף ${index - 1}`;
}

function getActiveStepId(progress) {
  if ((progress.percent ?? 0) >= 100 || progress.stage === "complete") {
    return "complete";
  }
  if (progress.stage === "compare" || progress.stage === "quality") {
    return "compare";
  }
  if (progress.stage === "scan") {
    return "scan";
  }
  if (progress.stage === "setup") {
    return "setup";
  }
  return "queued";
}

export function ScanPanel({
  form,
  normalizedFolderPaths,
  setForm,
  onSubmit,
  loading,
  progress,
  summary,
  error,
  runtimeInfo,
  onPickFolders,
  onPickPreferredRoot,
  onAddFolderRow,
  onRemoveFolderRow,
  onUpdateFolderPath,
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const activeStepId = getActiveStepId(progress);
  const activeStepIndex = SCAN_STEPS.findIndex((step) => step.id === activeStepId);
  const progressLabel = useMemo(() => (
    progress.percent >= 100
      ? "הסריקה הושלמה"
      : `שלב ${Math.max(activeStepIndex + 1, 1)} מתוך ${SCAN_STEPS.length}`
  ), [activeStepIndex, progress.percent]);

  return (
    <aside className="scan-panel">
      <div className="hero-section">
        <span className="eyebrow">Album Deduplicator</span>
        <h1>תיקיות ברורות, החלטות מהירות, מחיקה בטוחה.</h1>
        <p>
          הוסף roots בשדות נפרדים, בחר תיקייה מועדפת לשמירה, וקבל סביבת סקירה שמציגה רק את ההבדלים שחשובים באמת.
        </p>
        <div className="hero-runtime">
          <span className={`runtime-pill ${runtimeInfo?.isElectron ? "runtime-pill-desktop" : "runtime-pill-browser"}`}>
            {runtimeInfo?.isElectron ? "Electron + React" : "React + API"}
          </span>
          <span className="hero-runtime-text">
            {runtimeInfo?.isElectron
              ? `ה-backend המקומי מחובר דרך ${runtimeInfo.backendBaseUrl}`
              : "ב-browser ניתן להקליד נתיבים ידנית. ב-Electron אפשר גם לבחור תיקיות בדו-שיח מערכת."}
          </span>
        </div>
      </div>

      <form className="scan-form card" onSubmit={onSubmit}>
        <div className="scan-form-header">
          <div>
            <h3>הגדרת סריקה</h3>
            <p>כל שדה מייצג root נפרד. אפשר להתחיל עם שניים ולהוסיף עוד לפי הצורך.</p>
          </div>
          <div className="scan-form-tools">
            {runtimeInfo?.isElectron && (
              <Button type="button" variant="secondary" className="picker-btn" onClick={onPickFolders}>
                בחר כמה תיקיות
              </Button>
            )}
            <Button type="button" variant="ghost" className="picker-btn" onClick={() => onAddFolderRow("")}>
              הוסף שדה
            </Button>
          </div>
        </div>

        <div className="folder-fields">
          {form.folders.map((entry, index) => (
            <div key={entry.id} className="folder-row">
              <div className="folder-row-header">
                <label htmlFor={entry.id}>{getFolderLabel(index)}</label>
                <div className="folder-row-tools">
                  {form.folders.length > 1 && (
                    <button type="button" className="text-action-btn" onClick={() => onRemoveFolderRow(entry.id)}>
                      הסר
                    </button>
                  )}
                </div>
              </div>
              <input
                id={entry.id}
                aria-label={getFolderLabel(index)}
                type="text"
                placeholder={index === 0 ? "C:\\Music" : "D:\\Archive"}
                value={entry.path}
                onChange={(event) => onUpdateFolderPath(entry.id, event.target.value)}
              />
            </div>
          ))}
        </div>

        <div className="input-group">
          <div className="input-label-row">
            <label htmlFor="preferred-root">תיקייה מועדפת לשמירה</label>
            {runtimeInfo?.isElectron && (
              <Button type="button" variant="ghost" className="picker-btn" onClick={onPickPreferredRoot}>
                בחר תיקייה
              </Button>
            )}
          </div>
          <input
            id="preferred-root"
            aria-label="תיקייה מועדפת לשמירה"
            type="text"
            placeholder="בחר אחת מהתיקיות שהוזנו למעלה"
            value={form.preferred_root}
            onChange={(event) => setForm({ ...form, preferred_root: event.target.value })}
          />
          {normalizedFolderPaths.length > 0 && (
            <div className="folder-chip-list">
              {normalizedFolderPaths.map((path) => (
                <button
                  key={path}
                  type="button"
                  className={`folder-chip ${form.preferred_root === path ? "selected" : ""}`}
                  onClick={() => setForm({ ...form, preferred_root: path })}
                >
                  {path}
                </button>
              ))}
            </div>
          )}
          <p className="field-hint">המערכת תעדיף לשמור עותק מתוך root זה כאשר קיימים כמה עותקים דומים.</p>
        </div>

        <div className="form-actions">
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? "מנתח נתונים..." : "התחל סריקה חכמה"}
          </Button>
          <Button type="button" variant="ghost" onClick={() => setAdvancedOpen(!advancedOpen)}>
            {advancedOpen ? "הסתר הגדרות" : "הגדרות מתקדמות"}
          </Button>
        </div>

        {advancedOpen && (
          <div className="advanced-settings">
            <div className="input-group">
              <label htmlFor="bitrate-mode">יעד איכות למנוע ההשוואה</label>
              <select
                id="bitrate-mode"
                value={form.bitrate_mode}
                onChange={(event) => setForm({ ...form, bitrate_mode: event.target.value })}
              >
                <option value="128">Standard (128 kbps)</option>
                <option value="high">High (320 kbps)</option>
              </select>
            </div>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.force_rescan}
                onChange={(event) => setForm({ ...form, force_rescan: event.target.checked })}
              />
              אלץ סריקה מחדש מהדיסק
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.clear_cache}
                onChange={(event) => setForm({ ...form, clear_cache: event.target.checked })}
              />
              נקה זיכרון מטמון של השוואות
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.gemini_enabled}
                onChange={(event) => setForm({ ...form, gemini_enabled: event.target.checked })}
              />
              הפעל אימות AI (Gemini) למקרים גבוליים
            </label>
          </div>
        )}
      </form>

      <div className="status-card card">
        <div className="status-header">
          <div>
            <span className="status-overline">{progressLabel}</span>
            <h4 className="status-title">{progress.message}</h4>
            <p className="status-subtitle">{progress.human_message}</p>
          </div>
          <span className="status-percent">{progress.percent?.toFixed(0) ?? 0}%</span>
        </div>

        <div className="steps-strip" aria-label="התקדמות הסריקה">
          {SCAN_STEPS.map((step, index) => {
            const isComplete = index < activeStepIndex || progress.percent >= 100;
            const isActive = step.id === activeStepId;
            return (
              <div key={step.id} className={`step-pill ${isActive ? "active" : ""} ${isComplete ? "complete" : ""}`}>
                <span className="step-dot" />
                <span>{step.label}</span>
              </div>
            );
          })}
        </div>

        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress.percent ?? 0}%` }} />
        </div>

        {summary && (
          <div className="status-metrics">
            <span className="metric-pill safe-pill">{summary.counts.safe_clusters} בטוחות</span>
            <span className="metric-pill review-pill">{summary.counts.review_clusters} לסקירה</span>
            <span className="metric-pill neutral-pill">{summary.counts.compared_pairs} זוגות הושוו</span>
          </div>
        )}

        {error && <div className="alert-error">{error}</div>}
      </div>
    </aside>
  );
}
