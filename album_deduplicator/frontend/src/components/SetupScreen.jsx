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
        <section className="setup-hero-panel">
          <div className="setup-brand">
            <span className="setup-brand-kicker">Music Automatic</span>
            <h1>ניקוי ספריית מוזיקה בלי ניחושים</h1>
            <p>
              בוחרים תיקיות, מקבלים השוואה חכמה בין עותקים, ורק אז מחליטים מה למחוק. כל הזרימה בנויה כדי לקצר טעויות ולהבליט את ההבדלים החשובים באמת.
            </p>
          </div>

          <div className="setup-hero-orbit" aria-hidden="true">
            <div className="setup-orbit-ring setup-orbit-ring-primary" />
            <div className="setup-orbit-ring setup-orbit-ring-secondary" />
            <div className="setup-orbit-core">
              <span>Music</span>
              <strong>Automatic</strong>
            </div>
          </div>

          <div className="setup-feature-grid">
            <div className="setup-feature-card">
              <strong>השוואה לפי איכות</strong>
              <span>ביטרייט, עטיפה, גודל, שירים וחוסרים במקום אחד.</span>
            </div>
            <div className="setup-feature-card">
              <strong>המלצה ברורה</strong>
              <span>העותק המומלץ לשמירה מסומן מיד, עם אפשרות לאישור ידני.</span>
            </div>
            <div className="setup-feature-card">
              <strong>מחיקה בטוחה</strong>
              <span>סימון לסל המחזור בלבד, עם תצוגה מקדימה לפני ביצוע.</span>
            </div>
          </div>

          <div className="setup-runtime-strip">
            <div className="setup-runtime-chip">
              <span className={`setup-runtime-dot ${runtimeInfo?.isElectron ? "desktop" : "browser"}`} />
              {modeLabel}
            </div>
            <div className="setup-runtime-chip">RTL מותאם לעברית</div>
            <div className="setup-runtime-chip">זרימת review מהירה</div>
          </div>
        </section>

        <div className="setup-card">
          <div className="setup-card-header">
            <div className="icon-hero">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div>
              <h2>הגדרת סריקה</h2>
              <p>הוסף את הספריות שברצונך להשוות והתחל סריקה חכמה.</p>
            </div>
          </div>

          <form onSubmit={onSubmit}>
            <div className="form-section">
              <div className="form-section-header">
                <label style={{ margin: 0 }}>ספריות לסריקה</label>
                {runtimeInfo?.isElectron ? (
                  <Button type="button" variant="ghost" size="sm" style={{ height: '28px', fontSize: '0.8rem' }} onClick={onPickFolders}>
                    + בחר תיקיות
                  </Button>
                ) : (
                  <Button type="button" variant="ghost" size="sm" style={{ height: '28px', fontSize: '0.8rem' }} onClick={addFolder}>
                    + הוסף שורה
                  </Button>
                )}
              </div>
              <div className="form-helper">
                כל שורה היא root נפרד לסריקה. אפשר להשוות בין כמה ספריות במקביל.
              </div>
              <div className="path-list">
                {form.folders.map((folder, idx) => (
                  <div key={folder.id} className="path-input-group">
                    <span className="path-index">{idx + 1}</span>
                    <input
                      type="text"
                      className="path-input"
                      placeholder={idx === 0 ? "C:\\Music" : "D:\\Archive"}
                      value={folder.path}
                      onChange={(e) => handlePathChange(folder.id, e.target.value)}
                    />
                    {form.folders.length > 1 && (
                      <Button type="button" variant="ghost" size="icon" onClick={() => removeFolder(folder.id)} title="הסר שורה">
                        ✕
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="form-section">
              <label>תיקיית יעד מועדפת</label>
              <div className="form-helper">אם תרצה, אפשר לתת עדיפות לספרייה שבה בדרך כלל נשמרים העותקים הטובים יותר.</div>
              <div className="path-input-group">
                <input
                  type="text"
                  className="path-input"
                  placeholder="הנתיב שיקבל עדיפות"
                  value={form.preferred_root}
                  onChange={(e) => setForm({ ...form, preferred_root: e.target.value })}
                />
                {runtimeInfo?.isElectron && (
                  <Button type="button" variant="secondary" onClick={onPickPreferredRoot}>בחר</Button>
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
                  סריקה מחדש והתעלמות מה-Cache הקיים
                </label>
                <label className="checkbox-group">
                  <input type="checkbox" checked={form.gemini_enabled} onChange={(e) => setForm({...form, gemini_enabled: e.target.checked})} />
                  אימות AI למקרים גבוליים
                </label>
              </div>
            )}

            <div className="setup-submit-row">
              <div className="setup-submit-note">
                {hasFolders ? "המערכת תכין רשימת מחיקה רק אחרי בחירת עותק לשמירה." : "כדי להתחיל, הוסף לפחות ספרייה אחת."}
              </div>
              <Button type="submit" variant="primary" size="lg" style={{ width: '100%' }} disabled={!hasFolders}>
                התחל סריקה חכמה
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
