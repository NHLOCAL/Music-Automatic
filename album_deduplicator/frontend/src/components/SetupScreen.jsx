import React from "react";
import { Button, Checkbox, Input, Tag } from "antd";
import { Icon } from "./UI";

export function SetupScreen({ form, setForm, onSubmit, onPickFolders, runtimeInfo }) {
  const handlePathChange = (id, path) => {
    setForm((prev) => ({
      ...prev,
      folders: prev.folders.map((folder) => (folder.id === id ? { ...folder, path } : folder)),
    }));
  };

  const addFolder = () => {
    setForm((prev) => ({ ...prev, folders: [...prev.folders, { id: `manual-${Date.now()}`, path: "" }] }));
  };

  const removeFolder = (id) => {
    setForm((prev) => ({ ...prev, folders: prev.folders.filter((folder) => folder.id !== id) }));
  };

  const hasValidPath = form.folders.some(f => f.path.trim().length > 0);
  const runtimeLabel = runtimeInfo?.isElectron ? "Desktop" : "Browser";

  return (
    <div className="modal-backdrop">
      <div className="native-dialog">
        <div className="native-dialog-header">
          <div className="dialog-banner-strip">
            <Tag bordered={false} className="dialog-banner-chip">{runtimeLabel}</Tag>
            <Tag bordered={false} className="dialog-banner-chip dialog-banner-chip--accent">סל המחזור בלבד</Tag>
          </div>
          <h1>הגדרת סריקה - Music Automatic</h1>
          <p>בחר תיקיות לאיתור אלבומים כפולים</p>
        </div>
        
        <div className="native-dialog-body">
          <div className="setup-form-group">
            <label>תיקיות מקור:</label>
            <div className="folder-list-box">
              {form.folders.map((folder, index) => (
                <div key={folder.id} className="folder-list-item">
                  <Input 
                    aria-label={`תיקייה לסריקה ${index + 1}`}
                    variant="borderless" 
                    size="small" 
                    className="mono-text"
                    placeholder="נתיב לתיקייה..." 
                    value={folder.path} 
                    onChange={(e) => handlePathChange(folder.id, e.target.value)} 
                  />
                  {form.folders.length > 1 && (
                    <Button type="text" size="small" icon={<Icon name="x" size={12}/>} onClick={() => removeFolder(folder.id)} />
                  )}
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              {runtimeInfo?.isElectron && (
                <Button size="small" onClick={onPickFolders}>+ עיון...</Button>
              )}
              <Button size="small" onClick={addFolder}>+ הוסף שורה</Button>
            </div>
          </div>

          <div className="setup-form-group" style={{marginTop: 8}}>
            <label>הגדרות סריקה:</label>
            <div className="advanced-options">
              <Checkbox checked={form.full_hash_scan} onChange={(e) => setForm({...form, full_hash_scan: e.target.checked})}>
                <span style={{fontSize: 12}}>סריקת תוכן מלאה (Hash - מדויק אך איטי)</span>
              </Checkbox>
              <Checkbox checked={form.gemini_enabled} onChange={(e) => setForm({...form, gemini_enabled: e.target.checked})}>
                <span style={{fontSize: 12}}>הפעל אימות AI למקרים גבוליים</span>
              </Checkbox>
            </div>
          </div>
        </div>

        <div className="native-dialog-footer">
          <Button type="primary" onClick={onSubmit} disabled={!hasValidPath}>התחל סריקה</Button>
        </div>
      </div>
    </div>
  );
}
