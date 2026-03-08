import React, { useState } from "react";
import { Badge, Button, Icon } from "./UI";

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
          <div className="setup-brand-row">
            <div className="setup-brand-mark">
              <Icon name="sparkle" size={24} />
            </div>
            <div className="setup-brand">
              <h1>Music Automatic</h1>
              <p>ניקוי כפילויות חכם לאוסף המוזיקה שלך</p>
            </div>
            <Badge tone="success" icon="shield">Recycle Bin בלבד</Badge>
          </div>
          <div className="setup-trust-strip">
            <div className="setup-trust-item">
              <Icon name="folder" size={14} />
              כמה תיקיות שורש באותה סריקה
            </div>
            <div className="setup-trust-item">
              <Icon name="chart" size={14} />
              ניתוח איכות והשוואת ציונים
            </div>
            <div className="setup-trust-item">
              <Icon name="shield" size={14} />
              מחיקה בטוחה לסל המחזור בלבד
            </div>
          </div>
        </div>

        <form className="setup-body" onSubmit={onSubmit}>
          <div className="setup-section">
            <div className="setup-section-header">
              <label className="setup-section-title">
                <Icon name="folder" size={16} />
                תיקיות לסריקה
              </label>
              <div className="folder-actions">
                {runtimeInfo?.isElectron && (
                  <Button type="button" variant="secondary" size="sm" onClick={onPickFolders}>
                    <Icon name="plus" size={14} />
                    + בחר כמה תיקיות
                  </Button>
                )}
                <Button type="button" variant="ghost" size="sm" onClick={addFolder}>
                  <Icon name="plus" size={14} />
                  + הוסף שורה ידנית
                </Button>
              </div>
            </div>
            
            <div className="folder-list">
              {form.folders.map((folder, idx) => (
                <div key={folder.id} className="folder-row">
                  <div className="input-field input-field-path">
                     <Icon name="folder" size={16} className="input-leading-icon" />
                     <input
                        type="text"
                        aria-label={`תיקייה לסריקה ${idx + 1}`}
                        className="input-plain"
                        placeholder={`נתיב לתיקייה ${idx + 1}...`}
                        value={folder.path}
                        onChange={(e) => handlePathChange(folder.id, e.target.value)}
                     />
                  </div>
                  {form.folders.length > 1 && (
                    <Button type="button" variant="ghost" size="icon" onClick={() => removeFolder(folder.id)} title="הסר">
                      <Icon name="x" size={16} />
                    </Button>
                  )}
                </div>
              ))}
            </div>
            <p className="input-helper">ניתן לבחור מספר תיקיות שורש. המערכת תחפש כפילויות בין כל התיקיות.</p>
          </div>

          <div className="setup-section">
            <label className="setup-section-title">
              <Icon name="shield" size={16} />
              תיקייה מועדפת (אופציונלי)
            </label>
            <div className="folder-row">
               <div className="input-field input-field-path">
                 <Icon name="shield" size={16} className="input-leading-icon" />
                 <input
                    type="text"
                    aria-label="תיקייה מועדפת לשמירה"
                    className="input-plain"
                    placeholder="למשל: C:\Music\Best"
                    value={form.preferred_root}
                    onChange={(e) => setForm({ ...form, preferred_root: e.target.value })}
                 />
               </div>
               {runtimeInfo?.isElectron && (
                  <Button type="button" variant="secondary" onClick={onPickPreferredRoot}>
                    <Icon name="folder" size={14} />
                    עיון...
                  </Button>
               )}
            </div>
            <p className="input-helper">אם יימצא עותק בתיקייה זו, הוא יקבל עדיפות אוטומטית לשמירה.</p>
          </div>

          <div className="setup-section">
            <button type="button" className="advanced-trigger" onClick={() => setShowAdvanced(!showAdvanced)}>
              <span className="advanced-trigger-label">
                <Icon name="settings" size={15} />
                הגדרות מתקדמות
              </span>
              <Icon name="chevron-down" size={16} className={showAdvanced ? "chevron-open" : ""} />
            </button>

            {showAdvanced && (
              <div className="advanced-panel">
                <label className="checkbox-card">
                  <input
                    type="checkbox"
                    aria-label="סריקה מחדש מלאה"
                    checked={form.force_rescan}
                    onChange={(e) => setForm({...form, force_rescan: e.target.checked})}
                  />
                  <div className="checkbox-content">
                    <span className="checkbox-icon">
                      <Icon name="database" size={16} />
                    </span>
                    <h4>סריקה מחדש מלאה</h4>
                    <p>התעלם מנתונים שמורים ב-Cache וסרוק את הדיסק מחדש.</p>
                  </div>
                </label>
                <label className="checkbox-card">
                  <input
                    type="checkbox"
                    aria-label="סריקת Hash מלאה"
                    checked={form.full_hash_scan}
                    onChange={(e) => setForm({...form, full_hash_scan: e.target.checked})}
                  />
                  <div className="checkbox-content">
                    <span className="checkbox-icon">
                      <Icon name="compare" size={16} />
                    </span>
                    <h4>סריקת Hash מלאה</h4>
                    <p>חשב hash מלא לכל קובץ להשוואה מדויקת יותר. איטי יותר ולכן כבוי כברירת מחדל.</p>
                  </div>
                </label>
                <label className="checkbox-card">
                  <input
                    type="checkbox"
                    aria-label="אימות AI (Gemini)"
                    checked={form.gemini_enabled}
                    onChange={(e) => setForm({...form, gemini_enabled: e.target.checked})}
                  />
                  <div className="checkbox-content">
                    <span className="checkbox-icon">
                      <Icon name="sparkle" size={16} />
                    </span>
                    <h4>אימות AI (Gemini)</h4>
                    <p>השתמש בבינה מלאכותית להכרעה במקרים גבוליים.</p>
                  </div>
                </label>
              </div>
            )}
          </div>

          <div className="setup-footer">
            <span className={`setup-footer-state ${hasFolders ? "is-ready" : ""}`}>
              <Icon name={hasFolders ? "check-circle" : "alert"} size={14} />
              {hasFolders ? "מוכן לסריקה" : "יש להוסיף לפחות תיקייה אחת"}
            </span>
            <Button type="submit" variant="primary" size="lg" disabled={!hasFolders}>
              <Icon name="sparkle" size={16} />
              התחל סריקה חכמה
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
