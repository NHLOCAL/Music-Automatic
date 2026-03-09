import React from "react";
import { Card, Col, Progress, Row, Statistic, Typography } from "antd";

import { Icon } from "./UI";

export function ScanningScreen({ progress }) {
  const percent = Math.round(progress.percent || 0);
  const progressDetails = [
    {
      icon: "folder",
      label: "שלב פעיל",
      value: progress.stage || "scan",
    },
    {
      icon: "clock",
      label: "התקדמות",
      value: progress.total ? `${progress.current || 0}/${progress.total}` : `${percent}%`,
    },
    {
      icon: "shield",
      label: "מצב",
      value: percent >= 100 ? "מוכן לסקירה" : "מריץ ניתוח",
    },
  ];

  return (
    <div className="screen-center">
      <Card className="scanning-shell cartoon-card" variant="borderless">
        <div className="scanning-progress-wrap">
          <div className="soft-kicker">
            <Icon name="sparkle" size={14} />
            סריקה חכמה בתהליך
          </div>

          <Progress
            type="circle"
            percent={percent}
            strokeWidth={10}
            size={220}
            percentPosition={{ align: "center", type: "inner" }}
          />

          <div>
            <Typography.Title level={2} className="page-title" style={{ marginBottom: 8 }}>
              {progress.message}
            </Typography.Title>
            <Typography.Paragraph className="page-subtitle" style={{ margin: 0 }}>
              {progress.human_message}
            </Typography.Paragraph>
          </div>

          <Row gutter={[14, 14]} className="scanning-status-grid">
            {progressDetails.map((item) => (
              <Col key={item.label} xs={24} md={8}>
                <Card className="scanning-status-card cartoon-panel" variant="borderless">
                  <Icon name={item.icon} size={18} />
                  <Statistic title={item.label} value={item.value} />
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      </Card>
    </div>
  );
}
