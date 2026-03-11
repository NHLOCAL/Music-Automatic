import React, { useMemo, useState } from "react";
import { Button, Checkbox, Collapse, Input, Select, Tag } from "antd";
import { CloseOutlined, FolderOpenOutlined, PlusOutlined, StarOutlined } from "@ant-design/icons";

const ADVANCED_OPTIONS = [
  {
    key: "force_rescan",
    label: "רענון מלא מהדיסק",
    description: "מתעלם מהמידע השמור ומחשב מחדש את כל התיקיות שנבחרו.",
  },
  {
    key: "full_hash_scan",
    label: "בדיקת Hash מלאה",
    description: "משפרת דיוק בהשוואה בין עותקים, אך מאריכה את זמן הסריקה.",
  },
  {
    key: "gemini_enabled",
    label: "אימות AI למקרים גבוליים",
    description: "מוסיף בדיקת AI רק כשאין הכרעה ברורה בין העותקים.",
  },
];

export function SetupScreen({ form, setForm, onSubmit, onPickFolders, onPickFolder, runtimeInfo }) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const preferredFolderOptions = useMemo(
    () => form.folders
      .filter((folder) => folder.path.trim())
      .map((folder, index) => ({
        value: folder.id,
        label: `תיקייה ${index + 1} - ${folder.path.trim()}`,
      })),
    [form.folders],
  );

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
  const runtimeLabel = runtimeInfo?.isElectron ? "אפליקציית Windows" : "גרסת דפדפן";

  return (
    <div className="modal-backdrop">
      <div className="native-dialog">
        <div className="native-dialog-header">
          <div className="dialog-banner-strip">
            <Tag variant="filled" className="dialog-banner-chip">{runtimeLabel}</Tag>
            <Tag variant="filled" className="dialog-banner-chip dialog-banner-chip--accent">סל המחזור בלבד</Tag>
          </div>
          <p className="setup-eyebrow">הגדרת סריקה בטוחה</p>
          <h1>
            <span className="setup-brand-title">מיוזיק אוטומטיק</span>
            <span className="setup-title-subline">בחרו תיקיות לבדיקה והמערכת תאתר עבורכם אלבומים כפולים</span>
          </h1>
        </div>

        <div className="native-dialog-body">
          <div className="setup-form-group">
            <label>תיקיות לסריקה</label>
            <div className="folder-list-box">
              {form.folders.map((folder, index) => (
                <div key={folder.id} className="folder-list-item">
                  <Input
                    aria-label={`תיקייה לסריקה ${index + 1}`}
                    variant="borderless"
                    size="small"
                    className="mono-text"
                    placeholder={String.raw`למשל: C:\Music\Albums`}
                    value={folder.path}
                    onChange={(event) => handlePathChange(folder.id, event.target.value)}
                  />
                  {runtimeInfo?.isElectron ? (
                    <Button
                      size="small"
                      icon={<FolderOpenOutlined />}
                      className="folder-row-action folder-row-action--picker"
                      onClick={() => onPickFolder(folder.id, folder.path)}
                      aria-label={`בחר תיקייה עבור שורה ${index + 1}`}
                    >
                      בחר תיקייה
                    </Button>
                  ) : null}
                  {form.folders.length > 1 ? (
                    <Button
                      type="text"
                      size="small"
                      icon={<CloseOutlined />}
                      className="folder-row-action folder-row-action--remove"
                      onClick={() => removeFolder(folder.id)}
                      aria-label={`הסר תיקייה ${index + 1}`}
                    />
                  ) : null}
                </div>
              ))}
            </div>
            <div className="setup-helper-text">התחילו עם תיקייה אחת, והוסיפו עוד שורות רק אם יש עוד מקורות שחשוב להשוות.</div>
            <div className="setup-inline-actions">
              {runtimeInfo?.isElectron ? (
                <Button size="small" icon={<FolderOpenOutlined />} onClick={onPickFolders}>הוספת כמה תיקיות</Button>
              ) : null}
              <Button size="small" icon={<PlusOutlined />} onClick={addFolder}>הוסף תיקייה נוספת</Button>
            </div>
          </div>

          <div className="setup-form-group">
            <label>תיקייה מועדפת לשמירה</label>
            <div className="setup-preferred-row">
              <Select
                aria-label="תיקייה מועדפת לשמירה"
                size="small"
                allowClear
                className="setup-preferred-select"
                placeholder="ללא העדפה"
                value={form.preferred_folder_id || undefined}
                options={preferredFolderOptions}
                suffixIcon={<StarOutlined />}
                notFoundContent="הוסיפו קודם תיקיות פעילות לבחירה"
                optionFilterProp="label"
                onChange={(value) => setForm((prev) => ({ ...prev, preferred_folder_id: value ?? "" }))}
              />
            </div>
            <div className="setup-helper-text">הבחירה כאן עוזרת למערכת להעדיף איזו תיקייה לשמור כאשר נמצאות תיקיות כפולות או כמעט זהות.</div>
          </div>

          <div className="setup-form-group">
            <Collapse
              ghost
              activeKey={showAdvanced ? ["advanced"] : []}
              onChange={(keys) => setShowAdvanced(keys.length > 0)}
              items={[
                {
                  key: "advanced",
                  label: "הגדרות מתקדמות",
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
