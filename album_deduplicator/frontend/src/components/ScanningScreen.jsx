import React from "react";
import { Card, Progress, Typography } from "antd";

import { Icon, StatusTag } from "./UI";

const STAGE_FLOW = [
  {
    key: "setup",
    title: "מכין סביבת עבודה",
    description: "מאמת הגדרות, טוען cache ומכין את מנועי ההשוואה.",
    accent: "var(--colorPrimary)",
  },
  {
    key: "scan",
    title: "סורק תיקיות",
    description: "מזהה אלבומים, קורא metadata ובודק עטיפות וקבצי שמע.",
    accent: "#1f7a52",
  },
  {
    key: "quality",
    title: "מחשב איכות",
    description: "מדרג ביטרייט, שלמות metadata ואותות איכות נוספים.",
    accent: "#c9851e",
  },
  {
    key: "compare",
    title: "משווה ובונה קבוצות",
    description: "מחשב התאמות בין עותקים ומרכיב קבוצות בטוחות או לסקירה.",
    accent: "#7a55d1",
  },
];

function getStageIndex(stage) {
  const index = STAGE_FLOW.findIndex((item) => item.key === stage);
  if (stage === "complete") return STAGE_FLOW.length;
  return index >= 0 ? index : 0;
}

function getStageMeta(progress, percent) {
  const stageIndex = getStageIndex(progress.stage);
  if (percent >= 100 || progress.stage === "complete") {
    return {
      title: "הניתוח מוכן למעבר על התוצאות",
      description: "כל קבוצות ההשוואה הורכבו, והמערכת מוכנה למסך הסיכום והסקירה.",
      badge: "סיום ניתוח",
    };
  }

  const currentStage = STAGE_FLOW[Math.min(stageIndex, STAGE_FLOW.length - 1)];
  return {
    title: currentStage.title,
    description: currentStage.description,
    badge: "מנועי ההשוואה עובדים",
  };
}

function buildProgressDetails(progress, percent, stageMeta) {
  return [
    {
      icon: "folder",
      label: "שלב פעיל",
      value: stageMeta.title,
      hint: stageMeta.description,
    },
    {
      icon: "clock",
      label: "התקדמות",
      value: progress.total ? `${progress.current || 0}/${progress.total}` : `${percent}%`,
      hint: "המדד מבוסס על הפריטים שכבר עובדו בפועל.",
    },
    {
      icon: "shield",
      label: "מצב",
      value: percent >= 100 ? "מוכן לסקירה" : "ניתוח בלבד",
      hint: "בשלב הזה לא מתבצעת שום מחיקה או העברה לסל המחזור.",
    },
  ];
}

export function ScanningScreen({ progress }) {
  const percent = Math.round(progress.percent || 0);
  const stageIndex = getStageIndex(progress.stage);
  const stageMeta = getStageMeta(progress, percent);
  const progressDetails = buildProgressDetails(progress, percent, stageMeta);

  return (
    <div className="screen-center screen-center--compact">
      <Card className="scanning-shell cartoon-card" variant="borderless">
        <div className="scanning-progress-wrap">
          <div className="scanning-topline">
            <div className="soft-kicker">
              <Icon name="sparkle" size={14} />
              סריקה חכמה בתהליך
            </div>
            <StatusTag tone={percent >= 100 ? "success" : "primary"} icon={percent >= 100 ? "check-circle" : "clock"}>
              {stageMeta.badge}
            </StatusTag>
          </div>

          <div className="scanning-hero">
            <div className="scanning-progress-ring">
              <div className="scanning-orbit">
                <span className="scanning-orbit-dot dot-1" />
                <span className="scanning-orbit-dot dot-2" />
                <span className="scanning-orbit-dot dot-3" />
                <Progress
                  type="circle"
                  percent={percent}
                  strokeWidth={10}
                  size={220}
                  percentPosition={{ align: "center", type: "inner" }}
                />
              </div>
              <Typography.Text className="scanning-progress-caption">התקדמות כוללת</Typography.Text>
              <div className="scanning-equalizer" aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
                <span />
              </div>
            </div>

            <div className="scanning-copy-block">
              <Typography.Title level={1} className="page-title scanning-title">
                {progress.message || stageMeta.title}
              </Typography.Title>
              <Typography.Paragraph className="page-subtitle scanning-subtitle">
                {progress.human_message || stageMeta.description}
              </Typography.Paragraph>
              <div className="scanning-trust-note">
                <Icon name="shield" size={16} />
                רק ניתוח והשוואה. שום תיקייה לא נמחקת או מועברת בשלב הזה.
              </div>
            </div>
          </div>

          <div className="scanning-stage-strip" data-testid="scanning-stage-strip">
            {STAGE_FLOW.map((stage, index) => {
              const state = stageIndex > index || percent >= 100
                ? "done"
                : stageIndex === index
                  ? "active"
                  : "pending";
              return (
                <div key={stage.key} className={`scanning-stage-card is-${state}`}>
                  <div className="scanning-stage-index" style={{ "--stage-accent": stage.accent }}>
                    {state === "done" ? <Icon name="check-circle" size={13} /> : index + 1}
                  </div>
                  <div className="scanning-stage-copy">
                    <Typography.Text strong>{stage.title}</Typography.Text>
                    <Typography.Text type="secondary">{stage.description}</Typography.Text>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="scanning-status-grid" data-testid="scanning-status-grid">
            {progressDetails.map((item) => (
              <Card key={item.label} className="scanning-status-card cartoon-panel" variant="borderless">
                <div className="scanning-status-icon">
                  <Icon name={item.icon} size={18} />
                </div>
                <div className="scanning-status-copy">
                  <Typography.Text className="scanning-status-label" type="secondary">
                    {item.label}
                  </Typography.Text>
                  <Typography.Title level={4} className="scanning-status-value">
                    {item.value}
                  </Typography.Title>
                  <Typography.Text className="scanning-status-hint" type="secondary">
                    {item.hint}
                  </Typography.Text>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}
