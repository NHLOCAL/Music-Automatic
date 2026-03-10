import React, { useMemo, useState } from "react";
import { Button, Checkbox, Collapse, Input, Tag } from "antd";

const ADVANCED_OPTIONS = [
  {
    key: "force_rescan",
    label: "סריקה מחדש מלאה",
    description: "התעלם מה־cache וסרוק את התיקיות מחדש.",
  },
  {
    key: "full_hash_scan",
    label: "סריקת תוכן מלאה (Hash - מדויק אך איטי)",
    description: "משפר דיוק על חשבון זמן הסריקה.",
  },
  {
    key: "gemini_enabled",
    label: "הפעל אימות AI למקרים גבוליים",
    description: "מפעיל הכרעה נוספת רק למקרים לא חד-משמעיים.",
  },
];

export function SetupScreen({ form, setForm, onSubmit, onPickFolders, onPickPreferredRoot, runtimeInfo }) {
  const [showAdvanced, setShowAdvanced] = useState(false);

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

  const hasValidPath = useMemo(
    () => form.folders.some((folder) => folder.path.trim().length > 0),
    [form.folders],
  );
  const runtimeLabel = runtimeInfo?.isElectron ? "Desktop" : "Browser";

  return (
    <div className="modal-backdrop">
      <div className="native-dialog">
        <div className="native-dialog-header">
          <div className="dialog-banner-strip">
            <Tag variant="filled" className="dialog-banner-chip">{runtimeLabel}</Tag>
            <Tag variant="filled" className="dialog-banner-chip dialog-banner-chip--accent">סל המחזור בלבד</Tag>
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
                    onChange={(event) => handlePathChange(folder.id, event.target.value)}
                  />
                  {form.folders.length > 1 ? (
                    <Button type="text" size="small" onClick={() => removeFolder(folder.id)} aria-label={`הסר תיקייה ${index + 1}`}>
                      הסר
                    </Button>
                  ) : null}
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              {runtimeInfo?.isElectron ? (
                <Button size="small" onClick={onPickFolders}>+ עיון...</Button>
              ) : null}
              <Button size="small" onClick={addFolder}>+ הוסף שורה</Button>
            </div>
          </div>

          <div className="setup-form-group">
            <label>תיקייה מועדפת לשמירה:</label>
            <div className="folder-list-item setup-inline-row">
              <Input
                aria-label="תיקייה מועדפת לשמירה"
                variant="borderless"
                size="small"
                className="mono-text"
                placeholder="למשל: C:\\Music\\Best"
                value={form.preferred_root}
                onChange={(event) => setForm((prev) => ({ ...prev, preferred_root: event.target.value }))}
              />
              {runtimeInfo?.isElectron ? (
                <Button size="small" onClick={onPickPreferredRoot}>עיון...</Button>
              ) : null}
            </div>
          </div>

          <div className="setup-form-group">
            <Collapse
              ghost
              activeKey={showAdvanced ? ["advanced"] : []}
              onChange={(keys) => setShowAdvanced(keys.length > 0)}
              items={[
                {
                  key: "advanced",
                  label: "הגדרות",
                  children: (
                    <div className="advanced-options">
                      {ADVANCED_OPTIONS.map((option) => (
                        <Checkbox
                          key={option.key}
                          checked={Boolean(form[option.key])}
                          aria-label={option.label}
                          onChange={(event) => setForm((prev) => ({ ...prev, [option.key]: event.target.checked }))}
                        >
                          <div className="setup-option-copy">
                            <span>{option.label}</span>
                            <small>{option.description}</small>
                          </div>
                        </Checkbox>
                      ))}
                    </div>
                  ),
                },
              ]}
            />
          </div>
        </div>

        <div className="native-dialog-footer">
          <Button type="primary" onClick={onSubmit} disabled={!hasValidPath}>התחל סריקה</Button>
        </div>
      </div>
    </div>
  );
}
