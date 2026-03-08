import React, { useState } from "react";
import { Button } from "./UI";

export function ScanPanel({
  form,
  normalizedFolderPaths,
  setForm,
  onSubmit,
  loading,
  progress,
  summary,
  runtimeInfo,
  onPickFolders,
  onPickPreferredRoot,
  onAddFolderRow,
  onRemoveFolderRow,
  onUpdateFolderPath,
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const isComplete = progress.percent >= 100 || progress.stage === "complete";

  return (
    <aside className="scan-panel">
      <div className="hero-section">
        <span className="eyebrow">Album Deduplicator</span>
        <h2>סריקה וניקוי</h2>
        <p>בחר תיקיות לסריקה. המערכת תזהה אלבומים כפולים ותמליץ מה לשמור.</p>
        <div className="hero-runtime">
          <div className={`runtime-dot ${runtimeInfo?.isElectron ? "desktop" : "browser"}`} />
          <span>{runtimeInfo?.isElectron ? "Desktop Mode" : "Browser Mode"}</span>
        </div>
      </div>

      <form className="form-group" onSubmit={onSubmit}>
        <div className="form-group-header">
          <h4>תיקיות לסריקה</h4>
          {runtimeInfo?.isElectron && (
             <Button type="button" variant="ghost" onClick={onPickFolders} style={{ height: '28px', fontSize: '0.75rem' }}>
               + הוסף תיקיות
             </Button>
          )}
        </div>
        
        <div className="folder-list">
          {form.folders.map((entry, index) => (
            <div key={entry.id} className="folder-input-wrapper">
              <input
                type="text"
                placeholder={index === 0 ? "ספריית מקור (למשל C:\\Music)" : "ספריית יעד"}
                value={entry.path}
                onChange={(e) => onUpdateFolderPath(entry.id, e.target.value)}
                disabled={loading}
              />
              {form.folders.length > 1 && (
                <button type="button" className="icon-btn" onClick={() => onRemoveFolderRow(entry.id)} disabled={loading}>
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
        
        {!runtimeInfo?.isElectron && (
          <Button type="button" variant="ghost" onClick={() => onAddFolderRow("")} disabled={loading}>
            הוסף נתיב ידני
          </Button>
        )}

        <div className="form-group" style={{ marginTop: '16px' }}>
          <h4>תיקייה מועדפת (אופציונלי)</h4>
          <p className="field-hint">עותקים בנתיב זה יקבלו עדיפות שמירה.</p>
          <div className="folder-input-wrapper">
            <input
              type="text"
              placeholder="נתיב לשמירה מועדפת"
              value={form.preferred_root}
              onChange={(e) => setForm({ ...form, preferred_root: e.target.value })}
              disabled={loading}
            />
            {runtimeInfo?.isElectron && (
               <button type="button" className="icon-btn" onClick={onPickPreferredRoot} disabled={loading}>
                 ...
               </button>
            )}
          </div>
        </div>

        <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <Button type="submit" variant="primary" disabled={loading} style={{ width: '100%', height: '44px' }}>
            {loading ? "מנתח נתונים..." : "התחל סריקה"}
          </Button>
          <Button type="button" variant="ghost" onClick={() => setAdvancedOpen(!advancedOpen)} disabled={loading}>
            הגדרות מתקדמות
          </Button>
        </div>

        {advancedOpen && (
          <div className="advanced-settings">
            <label className="checkbox-label">
              <input type="checkbox" checked={form.force_rescan} onChange={(e) => setForm({ ...form, force_rescan: e.target.checked })} disabled={loading}/>
              סריקה מחדש מהדיסק (התעלם מ-Cache)
            </label>
            <label className="checkbox-label">
              <input type="checkbox" checked={form.gemini_enabled} onChange={(e) => setForm({ ...form, gemini_enabled: e.target.checked })} disabled={loading}/>
              אימות AI למקרים גבוליים (Gemini)
            </label>
            <div style={{ marginTop: '8px' }}>
               <span style={{ fontSize: '0.8125rem', color: 'var(--text-soft)', marginBottom: '4px', display: 'block' }}>איכות יעד להשוואה:</span>
               <select value={form.bitrate_mode} onChange={(e) => setForm({ ...form, bitrate_mode: e.target.value })} disabled={loading} style={{ width: '100%', padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--border-main)' }}>
                 <option value="128">Standard (128 kbps)</option>
                 <option value="high">High (320 kbps)</option>
               </select>
            </div>
          </div>
        )}
      </form>

      {(loading || isComplete) && (
        <div className="scan-progress-card">
          <div className="progress-circle-wrap">
            <svg className="progress-circle" viewBox="0 0 100 100">
              <circle className="progress-circle-bg" cx="50" cy="50" r="45" />
              <circle 
                className="progress-circle-bar" 
                cx="50" cy="50" r="45" 
                strokeDasharray="283" 
                strokeDashoffset={283 - (283 * (progress.percent || 0)) / 100} 
              />
            </svg>
            <div className="progress-percentage">{Math.round(progress.percent || 0)}%</div>
          </div>
          <div>
            <h4>{progress.message}</h4>
            <p style={{ marginTop: '4px' }}>{progress.human_message}</p>
          </div>
          {summary && isComplete && (
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
              <span className="badge badge-success">{summary.counts.safe_clusters} בטוחות</span>
              <span className="badge badge-warning">{summary.counts.review_clusters} לסקירה</span>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}