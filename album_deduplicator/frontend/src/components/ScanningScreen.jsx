import React from "react";
import { Card, Progress, Typography } from "antd";

import { Icon, StatusTag } from "./UI";

function buildProgressDetails(progress, percent) {
  return [
    {
      icon: "folder",
      label: "שלב פעיל",
      value: progress.stage || "scan",
      hint: "המערכת נעה בין סריקה, השוואה ובניית קבוצות.",
    },
    {
      icon: "clock",
      label: "התקדמות",
      value: progress.total ? `${progress.current || 0}/${progress.total}` : `${percent}%`,
      hint: "המדד מבוסס על הפריטים שעובדו עד עכשיו.",
    },
    {
      icon: "shield",
      label: "מצב",
      value: percent >= 100 ? "מוכן לסקירה" : "מריץ ניתוח",
      hint: "שום תיקייה לא מועברת בשלב הזה, רק נאסף מידע להשוואה.",
    },
  ];
}

export function ScanningScreen({ progress }) {
  const percent = Math.round(progress.percent || 0);
  const progressDetails = buildProgressDetails(progress, percent);

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
              {percent >= 100 ? "סיום ניתוח" : "מנועי ההשוואה עובדים"}
            </StatusTag>
          </div>

          <div className="scanning-hero">
            <div className="scanning-progress-ring">
              <Progress
                type="circle"
                percent={percent}
                strokeWidth={10}
                size={220}
                percentPosition={{ align: "center", type: "inner" }}
              />
              <Typography.Text className="scanning-progress-caption">
                התקדמות כוללת
              </Typography.Text>
            </div>

            <div className="scanning-copy-block">
              <Typography.Title level={1} className="page-title scanning-title">
                {progress.message}
              </Typography.Title>
              <Typography.Paragraph className="page-subtitle scanning-subtitle">
                {progress.human_message}
              </Typography.Paragraph>
              <div className="scanning-trust-note">
                <Icon name="shield" size={16} />
                רק ניתוח והשוואה. שום תיקייה לא נמחקת או מועברת בשלב הזה.
              </div>
            </div>
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
