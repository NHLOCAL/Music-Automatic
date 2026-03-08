import React, { useState } from "react";
import { Button } from "./UI";
export function ScanPanel({ form, setForm, onSubmit, loading, progress, summary, error }) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  return (
    <aside className="scan-panel">
      <div className="hero-section">
        <span className="eyebrow">Album Deduplicator</span>
        <h1>סדר באוסף המוזיקה בראש שקט</h1>
        <p>מזהה כפילויות, משווה איכויות ומשאיר אצלך שליטה מלאה על מה שנמחק.</p>
      </div>
      <form className="scan-form card" onSubmit={onSubmit}>
        <div className="input-group">
          <label>תיקיות לסריקה</label>
          <textarea
            rows={4}
            placeholder="C:\Music&#10;D:\Archive"
            value={form.folders}
            onChange={(e) => setForm({ ...form, folders: e.target.value })}
          />
        </div>
        <div className="input-group">
          <label>תיקייה מועדפת לשמירה (אופציונלי)</label>
          <input
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