import React, { useMemo, useState } from "react";
import { Alert, Button, Card, Checkbox, Collapse, Flex, Input, Space, Typography } from "antd";

import { Icon, StatusTag } from "./UI";

const TRUST_ITEMS = [
  { icon: "folder", text: "כמה תיקיות שורש באותה סריקה" },
  { icon: "chart", text: "ניתוח איכות והשוואת ציונים" },
  { icon: "shield", text: "מחיקה בטוחה לסל המחזור בלבד" },
];

const ADVANCED_OPTIONS = [
  {
    key: "force_rescan",
    label: "סריקה מחדש מלאה",
    description: "התעלם מנתונים שמורים ב-Cache וסרוק את הדיסק מחדש.",
    icon: "database",
    ariaLabel: "סריקה מחדש מלאה",
  },
  {
    key: "full_hash_scan",
    label: "סריקת Hash מלאה",
    description: "חשב hash מלא לכל קובץ להשוואה מדויקת יותר. איטי יותר ולכן כבוי כברירת מחדל.",
    icon: "compare",
    ariaLabel: "סריקת Hash מלאה",
  },
  {
    key: "gemini_enabled",
    label: "אימות AI (Gemini)",
    description: "השתמש בבינה מלאכותית להכרעה במקרים גבוליים.",
    icon: "sparkle",
    ariaLabel: "אימות AI (Gemini)",
  },
];

export function SetupScreen({ form, setForm, onSubmit, onPickFolders, onPickPreferredRoot, runtimeInfo }) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const hasFolders = useMemo(
    () => form.folders.some((folder) => folder.path.trim()),
    [form.folders],
  );

  const handlePathChange = (id, path) => {
    setForm((prev) => ({
      ...prev,
      folders: prev.folders.map((folder) => (folder.id === id ? { ...folder, path } : folder)),
    }));
  };

  const addFolder = () => {
    setForm((prev) => ({
      ...prev,
      folders: [...prev.folders, { id: `manual-${Date.now()}`, path: "" }],
    }));
  };

  const removeFolder = (id) => {
    setForm((prev) => ({
      ...prev,
      folders: prev.folders.filter((folder) => folder.id !== id),
    }));
  };

  return (
    <div className="screen-center">
      <Card className="setup-shell cartoon-card" variant="borderless">
        <div className="setup-hero">
          <div className="setup-brand">
            <div className="setup-brand-main">
              <div className="setup-brand-mark">
                <Icon name="sparkle" size={28} />
              </div>
              <div>
                <Typography.Title level={1} className="page-title" style={{ margin: 0 }}>
                  Music Automatic
                </Typography.Title>
                <Typography.Paragraph className="page-subtitle" style={{ margin: "6px 0 0" }}>
                  ניקוי כפילויות חכם לאוסף המוזיקה שלך
                </Typography.Paragraph>
              </div>
            </div>
            <StatusTag tone="success" icon="shield">
              Recycle Bin בלבד
            </StatusTag>
          </div>

          <div className="trust-strip">
            {TRUST_ITEMS.map((item) => (
              <div key={item.text} className="trust-item">
                <Icon name={item.icon} size={16} />
                <span>{item.text}</span>
              </div>
            ))}
          </div>

          <form onSubmit={onSubmit}>
            <div className="setup-grid">
              <Card
                className="setup-section-card cartoon-panel"
                title={(
                  <Flex align="center" gap={10}>
                    <Icon name="folder" size={18} />
                    <span>תיקיות לסריקה</span>
                  </Flex>
                )}
                variant="borderless"
              >
                <div className="setup-section-head">
                  <Typography.Paragraph className="muted-copy" style={{ margin: 0 }}>
                    ניתן לבחור מספר תיקיות שורש. המערכת תחפש כפילויות בין כל התיקיות.
                  </Typography.Paragraph>
                  <div className="folder-actions">
                    {runtimeInfo?.isElectron && (
                      <Button type="default" icon={<Icon name="plus" size={14} />} onClick={onPickFolders}>
                        + בחר כמה תיקיות
                      </Button>
                    )}
                    <Button type="default" icon={<Icon name="plus" size={14} />} onClick={addFolder}>
                      + הוסף שורה ידנית
                    </Button>
                  </div>
                </div>

                <div className="folder-list">
                  {form.folders.map((folder, index) => (
                    <div key={folder.id} className="folder-row">
                      <Input
                        size="large"
                        prefix={<Icon name="folder" size={16} />}
                        aria-label={`תיקייה לסריקה ${index + 1}`}
                        placeholder={`נתיב לתיקייה ${index + 1}...`}
                        value={folder.path}
                        onChange={(event) => handlePathChange(folder.id, event.target.value)}
                      />
                      {form.folders.length > 1 && (
                        <Button
                          aria-label={`הסר תיקייה ${index + 1}`}
                          icon={<Icon name="x" size={14} />}
                          onClick={() => removeFolder(folder.id)}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </Card>

              <Card
                className="setup-section-card cartoon-panel"
                title={(
                  <Flex align="center" gap={10}>
                    <Icon name="shield" size={18} />
                    <span>תיקייה מועדפת (אופציונלי)</span>
                  </Flex>
                )}
                variant="borderless"
              >
                <div className="folder-row">
                  <Input
                    size="large"
                    prefix={<Icon name="shield" size={16} />}
                    aria-label="תיקייה מועדפת לשמירה"
                    placeholder={"למשל: C:\\Music\\Best"}
                    value={form.preferred_root}
                    onChange={(event) => setForm({ ...form, preferred_root: event.target.value })}
                  />
                  {runtimeInfo?.isElectron && (
                    <Button type="default" icon={<Icon name="folder" size={14} />} onClick={onPickPreferredRoot}>
                      עיון...
                    </Button>
                  )}
                </div>
                <Typography.Paragraph className="muted-copy" style={{ margin: 0 }}>
                  אם יימצא עותק בתיקייה זו, הוא יקבל עדיפות אוטומטית לשמירה.
                </Typography.Paragraph>
              </Card>

              <Collapse
                activeKey={showAdvanced ? ["advanced"] : []}
                className="cartoon-panel"
                onChange={(keys) => setShowAdvanced(keys.length > 0)}
                items={[
                  {
                    key: "advanced",
                    label: (
                      <Flex align="center" gap={10}>
                        <Icon name="settings" size={16} />
                        <span>הגדרות מתקדמות</span>
                      </Flex>
                    ),
                    children: (
                      <div className="advanced-option-grid">
                        {ADVANCED_OPTIONS.map((option) => (
                          <Card key={option.key} className="advanced-option-card" variant="borderless">
                            <Checkbox
                              checked={form[option.key]}
                              aria-label={option.ariaLabel}
                              onChange={(event) => setForm({ ...form, [option.key]: event.target.checked })}
                            >
                              <div className="advanced-option-content">
                                <Space size={10} align="center">
                                  <Icon name={option.icon} size={16} />
                                  <Typography.Text strong>{option.label}</Typography.Text>
                                </Space>
                                <Typography.Text type="secondary">{option.description}</Typography.Text>
                              </div>
                            </Checkbox>
                          </Card>
                        ))}
                      </div>
                    ),
                  },
                ]}
              />

              <div className="setup-footer">
                <div className={`setup-footer-state ${hasFolders ? "is-ready" : ""}`}>
                  <Icon name={hasFolders ? "check-circle" : "alert"} size={16} />
                  <span>{hasFolders ? "מוכן לסריקה" : "יש להוסיף לפחות תיקייה אחת"}</span>
                </div>
                <Button
                  type="primary"
                  size="large"
                  icon={<Icon name="sparkle" size={16} />}
                  htmlType="submit"
                  disabled={!hasFolders}
                >
                  התחל סריקה חכמה
                </Button>
              </div>

              {!runtimeInfo?.isElectron && (
                <Alert
                  type="info"
                  showIcon
                  title="מצב דפדפן"
                  description="בחירת התיקיות מתבצעת ידנית כי האפליקציה כרגע לא רצה בתוך Electron."
                />
              )}
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
}
