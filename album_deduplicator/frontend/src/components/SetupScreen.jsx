import React, { useState } from "react";
import { Button } from "./UI";

export function SetupScreen({ form, setForm, onSubmit, onPickFolders, onPickPreferredRoot, runtimeInfo }) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const hasFolders = form.folders.some((folder) => folder.path.trim());

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
      <div className="setup-container">
        <div className="setup-header">
          <div className="setup-brand">
            <h1>Music Automatic</h1>
            <p>ניקוי כפילויות חכם לאוסף המוזיקה שלך</p>
          </div>
        </div>

        <form className="setup-body" onSubmit={onSubmit}>
          {/* Folders Section */}
          <div className="setup-section">
            <div className="setup-section-header">
              <label className="setup-section-title">תיקיות לסריקה</label>
              <div className="folder-actions">
                {runtimeInfo?.isElectron && (
                  <Button type="button" variant="secondary" size="sm" onClick={onPickFolders}>
                    + בחר תיקיות (Browser)
                  </Button>
                )}
                <Button type="button" variant="ghost" size="sm" onClick={addFolder}>
                  + הוסף שורה ידנית
                </Button>
              </div>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {form.folders.map((folder, idx) => (
                <div key={folder.id} className="folder-row">
                  <div className="input-field" style={{ display: 'flex', alignItems: 'center' }}>
                     <input
                        type="text"
                        style={{ border: 'none', background: 'transparent', width: '100%', height: '100%', outline: 'none' }}
                        placeholder={`נתיב לתיקייה ${idx + 1}...`}
                        value={folder.path}
                        onChange={(e) => handlePathChange(folder.id, e.target.value)}
                     />
                  </div>
                  {form.folders.length > 1 && (
                    <Button type="button" variant="ghost" size="icon" onClick={() => removeFolder(folder.id)} title="הסר">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </Button>
                  )}
                </div>
              ))}
            </div>
            <p className="input-helper">ניתן לבחור מספר תיקיות שורש. המערכת תחפש כפילויות בין כל התיקיות.</p>
          </div>

          {/* Preferred Root Section */}
          <div className="setup-section">
            <label className="setup-section-title">תיקייה מועדפת (אופציונלי)</label>
            <div className="folder-row">
               <div className="input-field" style={{ display: 'flex', alignItems: 'center' }}>
                 <input
                    type="text"
                    style={{ border: 'none', background: 'transparent', width: '100%', height: '100%', outline: 'none' }}
                    placeholder="למשל: C:\Music\Best"
                    value={form.preferred_root}
                    onChange={(e) => setForm({ ...form, preferred_root: e.target.value })}
                 />
               </div>
               {runtimeInfo?.isElectron && (
                  <Button type="button" variant="secondary" onClick={onPickPreferredRoot}>עיון...</Button>
               )}
            </div>
            <p className="input-helper">אם יימצא עותק בתיקייה זו, הוא יקבל עדיפות אוטומטית לשמירה.</p>
          </div>

          {/* Advanced Section */}
          <div className="setup-section">
            <div className="advanced-trigger" onClick={() => setShowAdvanced(!showAdvanced)}>
              <span>הגדרות מתקדמות</span>
              <svg 
                width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                style={{ transform: showAdvanced ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s' }}
              >
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>

            {showAdvanced && (
              <div className="advanced-panel">
                <label className="checkbox-card">
                  <input type="checkbox" checked={form.force_rescan} onChange={(e) => setForm({...form, force_rescan: e.target.checked})} />
                  <div className="checkbox-content">
                    <h4>סריקה מחדש מלאה</h4>
                    <p>התעלם מנתונים שמורים ב-Cache וסרוק את הדיסק מחדש.</p>
                  </div>
                </label>
                <label className="checkbox-card">
                  <input type="checkbox" checked={form.gemini_enabled} onChange={(e) => setForm({...form, gemini_enabled: e.target.checked})} />
                  <div className="checkbox-content">
                    <h4>אימות AI (Gemini)</h4>
                    <p>השתמש בבינה מלאכותית להכרעה במקרים גבוליים.</p>
                  </div>
                </label>
              </div>
            )}
          </div>

          <div className="setup-footer">
            <span style={{ color: hasFolders ? 'var(--color-success-text)' : 'var(--text-tertiary)', fontSize: '0.9rem' }}>
              {hasFolders ? "מוכן לסריקה" : "יש להוסיף לפחות תיקייה אחת"}
            </span>
            <Button type="submit" variant="primary" size="lg" disabled={!hasFolders}>
              התחל סריקה חכמה
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}