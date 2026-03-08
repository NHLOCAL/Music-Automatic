import React, { useState } from "react";
import { Button } from "./UI";

export function ScanPanel({
  form,
  setForm,
  onSubmit,
  loading,
  progress,
  summary,
  error,
  runtimeInfo,
  onPickFolders,
  onPickPreferredRoot,
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  return (
    <aside className="scan-panel">
      <div className="hero-section">
        <span className="eyebrow">Album Deduplicator</span>
        <h1>סדר באוסף המוזיקה בראש שקט</h1>
        <p>מזהה כפילויות, משווה איכויות ומשאיר אצלך שליטה מלאה על מה שנמחק.</p>
        <div className="hero-runtime">
          <span className={`runtime-pill ${runtimeInfo?.isElectron ? "runtime-pill-desktop" : "runtime-pill-browser"}`}>
            {runtimeInfo?.isElectron ? "Electron + React" : "React + API"}
          </span>
          <span className="hero-runtime-text">
            {runtimeInfo?.isElectron
              ? `ה-backend המקומי מחובר דרך ${runtimeInfo.backendBaseUrl}`
              : "אפשר להקליד נתיבים ידנית או להפעיל את מעטפת Electron לחוויית Desktop מלאה."}
          </span>
        </div>
      </div>
      <form className="scan-form card" onSubmit={onSubmit}>
        <div className="input-group">
          <div className="input-label-row">
            <label htmlFor="scan-folders">תיקיות לסריקה</label>
            {runtimeInfo?.isElectron && (
              <Button type="button" variant="secondary" className="picker-btn" onClick={onPickFolders}>
                בחר תיקיות
              </Button>
            )}
          </div>
          <textarea
            id="scan-folders"
            aria-label="תיקיות לסריקה"
            rows={4}
            placeholder="C:\Music&#10;D:\Archive"
            value={form.folders}
            onChange={(e) => setForm({ ...form, folders: e.target.value })}
          />
          <p className="field-hint">כל שורה היא root נפרד לסריקה.</p>
        </div>
        <div className="input-group">
          <div className="input-label-row">
            <label htmlFor="preferred-root">תיקייה מועדפת לשמירה (אופציונלי)</label>
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
            placeholder="לדוגמה: C:\Music"
            value={form.preferred_root}
            onChange={(e) => setForm({ ...form, preferred_root: e.target.value })}
          />
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
              <label>יעד איכות למנוע השוואה</label>
              <select value={form.bitrate_mode} onChange={(e) => setForm({ ...form, bitrate_mode: e.target.value })}>
                <option value="128">Standard (128 kbps)</option>
                <option value="high">High (320 kbps)</option>
              </select>
            </div>
            <label className="checkbox-label">
              <input type="checkbox" checked={form.force_rescan} onChange={(e) => setForm({ ...form, force_rescan: e.target.checked })} />
              אלץ סריקה מחדש מהדיסק
            </label>
            <label className="checkbox-label">
              <input type="checkbox" checked={form.clear_cache} onChange={(e) => setForm({ ...form, clear_cache: e.target.checked })} />
              נקה זכרון מטמון של השוואות
            </label>
            <label className="checkbox-label">
              <input type="checkbox" checked={form.gemini_enabled} onChange={(e) => setForm({ ...form, gemini_enabled: e.target.checked })} />
              הפעל אימות AI (Gemini) למקרים גבוליים
            </label>
          </div>
        )}
      </form>
      <div className="status-card card">
        <div className="status-header">
          <div>
            <h4 className="status-title">{progress.message}</h4>
            <p className="status-subtitle">{progress.human_message}</p>
          </div>
          <span className="status-percent">{progress.percent?.toFixed(0) ?? 0}%</span>
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress.percent ?? 0}%` }} />
        </div>
        {summary && (
          <div className="status-metrics">
            <span className="metric-pill safe-pill">{summary.counts.safe_clusters} בטוחות</span>
            <span className="metric-pill review-pill">{summary.counts.review_clusters} לסקירה</span>
          </div>
        )}
        {error && <div className="alert-error">{error}</div>}
      </div>
    </aside>
  );
}
