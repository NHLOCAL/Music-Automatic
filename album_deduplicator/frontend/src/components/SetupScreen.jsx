import React, { useState } from "react";
import { Button } from "./UI";

export function SetupScreen({ form, setForm, onSubmit, onPickFolders, onPickPreferredRoot, runtimeInfo }) {
  const [showAdvanced, setShowAdvanced] = useState(false);

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
      <div className="setup-card">
        <div className="icon-hero">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </div>
        <h1>מציאת כפילויות חכמה</h1>
        <p>בחר את התיקיות שברצונך לסרוק. המערכת תזהה אלבומים כפולים ותמליץ על העותק האיכותי ביותר.</p>
        
        <form onSubmit={onSubmit}>
          <div className="form-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label style={{ margin: 0 }}>ספריות לסריקה</label>
              {runtimeInfo?.isElectron && (
                <Button type="button" variant="ghost" size="sm" style={{ height: '24px', fontSize: '0.75rem' }} onClick={onPickFolders}>
                  + בחר תיקיות
                </Button>
              )}
            </div>
            <div className="path-list">
              {form.folders.map((folder, idx) => (
                <div key={folder.id} className="path-input-group">
                  <input
                    type="text"
                    className="path-input"
                    placeholder={idx === 0 ? "C:\\Music" : "D:\\Archive"}
                    value={folder.path}
                    onChange={(e) => handlePathChange(folder.id, e.target.value)}
                  />
                  {form.folders.length > 1 && (
                    <Button type="button" variant="ghost" size="icon" onClick={() => removeFolder(folder.id)}>✕</Button>
                  )}
                </div>
              ))}
            </div>
            {!runtimeInfo?.isElectron && (
              <Button type="button" variant="ghost" style={{ marginTop: '8px', width: '100%' }} onClick={addFolder}>
                + הוסף נתיב
              </Button>
            )}
          </div>

          <div className="form-section">
            <label>תיקיית יעד מועדפת (אופציונלי)</label>
            <div className="path-input-group">
              <input
                type="text"
                className="path-input"
                placeholder="הנתיב שיקבל עדיפות"
                value={form.preferred_root}
                onChange={(e) => setForm({ ...form, preferred_root: e.target.value })}
              />
              {runtimeInfo?.isElectron && (
                <Button type="button" variant="secondary" onClick={onPickPreferredRoot}>...</Button>
              )}
            </div>
          </div>

          <div className="advanced-toggle" onClick={() => setShowAdvanced(!showAdvanced)}>
            <span>הגדרות מתקדמות</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: showAdvanced ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>

          {showAdvanced && (
            <div className="advanced-panel">
              <label className="checkbox-group">
                <input type="checkbox" checked={form.force_rescan} onChange={(e) => setForm({...form, force_rescan: e.target.checked})} />
                סריקה מחדש (התעלם מ-Cache)
              </label>
              <label className="checkbox-group">
                <input type="checkbox" checked={form.gemini_enabled} onChange={(e) => setForm({...form, gemini_enabled: e.target.checked})} />
                אימות AI למקרים גבוליים (Gemini)
              </label>
            </div>
          )}

          <Button type="submit" variant="primary" size="lg" style={{ width: '100%' }} disabled={!form.folders.some(f => f.path.trim())}>
            התחל סריקה
          </Button>
        </form>
      </div>
    </div>
  );
}