import React, { useMemo, useState } from "react";
import { Button, Checkbox, Collapse, Input, Tag } from "antd";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CloseOutlined,
  FolderOpenOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  SettingOutlined,
} from "@ant-design/icons";

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

  const moveFolder = (id, direction) => {
    setForm((prev) => {
      const currentIndex = prev.folders.findIndex((folder) => folder.id === id);
      const nextIndex = currentIndex + direction;
      if (currentIndex < 0 || nextIndex < 0 || nextIndex >= prev.folders.length) return prev;
      const folders = [...prev.folders];
      [folders[currentIndex], folders[nextIndex]] = [folders[nextIndex], folders[currentIndex]];
      return { ...prev, folders };
    });
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
                  <div className="preference-rank-badge" aria-hidden="true">{index + 1}</div>
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
                  <Button
                    type="text"
                    size="small"
                    icon={<ArrowUpOutlined />}
                    className="folder-row-action folder-row-action--order"
                    onClick={() => moveFolder(folder.id, -1)}
                    disabled={index === 0}
                    aria-label={`העלה את תיקייה ${index + 1} בסדר ההעדפה`}
                  />
                  <Button
                    type="text"
                    size="small"
                    icon={<ArrowDownOutlined />}
                    className="folder-row-action folder-row-action--order"
                    onClick={() => moveFolder(folder.id, 1)}
                    disabled={index === form.folders.length - 1}
                    aria-label={`הורד את תיקייה ${index + 1} בסדר ההעדפה`}
                  />
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
            <div className="setup-helper-text">סדר השורות הוא סדר ההעדפה: תיקייה עליונה עדיפה על זו שמתחתיה, גם עבור תתי-תיקיות שנמצאות בתוכה.</div>
            <div className="setup-inline-actions">
              {runtimeInfo?.isElectron ? (
                <Button size="small" icon={<FolderOpenOutlined />} onClick={onPickFolders} aria-label="הוספת כמה תיקיות">
                  הוספת כמה תיקיות
                </Button>
              ) : null}
              <Button size="small" icon={<PlusOutlined />} onClick={addFolder} aria-label="הוסף תיקייה נוספת">
                הוסף תיקייה נוספת
              </Button>
            </div>
          </div>

          <div className="setup-form-group">
            <label>סדר עדיפות לשמירה</label>
            <Checkbox
              checked={form.use_preferred_roots}
              aria-label="הפעל סדר עדיפות לשמירה"
              onChange={(event) => setForm((prev) => ({ ...prev, use_preferred_roots: event.target.checked }))}
            >
              <div className="setup-option-copy">
                <span>הפעל סדר עדיפות לשמירה</span>
                <small>כבוי: המערכת תבחר לפי איכות בלבד, בלי להעדיף root מסוים.</small>
              </div>
            </Checkbox>
            <div className="setup-helper-text">כאשר נמצאים עותקים זהים או באותה איכות, המערכת תשמור את העותק שנמצא תחת התיקייה שמופיעה מוקדם יותר בסדר.</div>
          </div>

          <div className="setup-form-group">
            <Collapse
              ghost
              activeKey={showAdvanced ? ["advanced"] : []}
              onChange={(keys) => setShowAdvanced(keys.length > 0)}
              items={[
                {
                  key: "advanced",
                  label: (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <SettingOutlined />
                      <span>הגדרות מתקדמות</span>
                    </span>
                  ),
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
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={onSubmit}
            disabled={!hasValidPath}
            aria-label="התחל סריקה"
          >
            התחל סריקה
          </Button>
        </div>
      </div>
    </div>
  );
}
