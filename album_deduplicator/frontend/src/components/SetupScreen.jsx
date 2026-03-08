import React, { useState } from "react";
import { Button } from "./UI";

export function SetupScreen({ form, setForm, onSubmit, onPickFolders, onPickPreferredRoot, runtimeInfo }) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const hasFolders = form.folders.some((folder) => folder.path.trim());
  const modeLabel = runtimeInfo?.isElectron ? "אפליקציית Desktop" : "דפדפן";

  const handlePathChange = (id, path) => {
    setForm(prev => ({
      ...prev,
      folders: prev.folders.map(f => f.id === id ? { ...f, path } : f)
    }));
  };

  const addFolder = () => {
    setForm(prev => ({
      ...prev,
      folders: [...prev.folders, { id: `manual-${Date.now()}`, path: "" }]
    }));
  };

  const removeFolder = (id) => {
    setForm(prev => ({
      ...prev,
      folders: prev.folders.filter(f => f.id !== id)
    }));
  };

  return (
    <div className="centered-view">
      <div className="setup-shell">
        <div className="setup-header">
          <div className="setup-header-content">
            <h1>Music Automatic</h1>
            <p>הגדרת סריקה לאיתור אלבומים כפולים ופינוי שטח אחסון בביטחון מלא.</p>
          </div>
          <div className="setup-runtime-badge">
            <span className={`setup-runtime-dot ${runtimeInfo?.isElectron ? "desktop" : ""}`} />
            {modeLabel}
          </div>
        </div>

        <div className="setup-body">
          <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            <div className="form-section">
              <div className="form-section-header">
                <label>תיקיות לסריקה</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {runtimeInfo?.isElectron && (
                    <Button type="button" variant="secondary" size="sm" onClick={onPickFolders}>
                      בחירת תיקיות
                    </Button>
                  )}
                  <Button type="button" variant="ghost" size="sm" onClick={addFolder}>
                    + נתיב ידני
                  </Button>
                </div>
              </div>
              <div className="form-helper">
                בחר את תיקיות השורש המכילות את אוסף המוזיקה שלך. ניתן להוסיף מספר תיקיות במקביל.
              </div>
              <div className="path-list">
                {form.folders.map((folder, idx) => (
                  <div key={folder.id} className="path-input-group">
                    <input
                      type="text"
                      className="path-input"
                      placeholder={`נתיב לתיקייה ${idx + 1}`}
                      value={folder.path}
                      onChange={(e) => handlePathChange(folder.id, e.target.value)}
                    />
                    {form.folders.length > 1 && (
                      <Button type="button" variant="ghost" size="icon" onClick={() => removeFolder(folder.id)} title="הסר תיקייה">
                        ✕
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="form-section">
              <label>שמירה מועדפת (אופציונלי)</label>
              <div className="form-helper">הגדר נתיב מועדף. אם יימצא עותק כפול בנתיב זה, המערכת תעדיף לשמור אותו.</div>
              <div className="path-input-group">
                <input
                  type="text"
                  className="path-input"
                  placeholder="לדוגמה: C:\Music\Archive"
                  value={form.preferred_root}
                  onChange={(e) => setForm({ ...form, preferred_root: e.target.value })}
                />
                {runtimeInfo?.isElectron && (
                  <Button type="button" variant="secondary" onClick={onPickPreferredRoot}>עיון</Button>
                )}
              </div>
            </div>

            <div className="form-section">
              <div className="advanced-toggle" onClick={() => setShowAdvanced(!showAdvanced)}>
                <span>הגדרות סריקה מתקדמות</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: showAdvanced ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </div>
              {showAdvanced && (
                <div className="advanced-panel">
                  <label className="checkbox-group">
                    <input type="checkbox" checked={form.force_rescan} onChange={(e) => setForm({...form, force_rescan: e.target.checked})} />
                    <span>סריקה מלאה מחדש (התעלמות ממטמון קיים)</span>
                  </label>
                  <label className="checkbox-group">
                    <input type="checkbox" checked={form.gemini_enabled} onChange={(e) => setForm({...form, gemini_enabled: e.target.checked})} />
                    <span>אימות AI (Gemini) למקרים גבוליים</span>
                  </label>
                </div>
              )}
            </div>

            <div className="setup-submit-row">
              <span className="form-helper">
                {hasFolders ? "המערכת תסרוק את התיקיות ותציג המלצות לפני מחיקה." : "יש להזין לפחות נתיב אחד כדי להתחיל."}
              </span>
              <Button type="submit" variant="primary" size="lg" disabled={!hasFolders}>
                התחל סריקה
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}