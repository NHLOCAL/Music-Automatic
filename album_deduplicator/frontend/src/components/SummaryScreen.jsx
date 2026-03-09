import React from "react";
import { Alert, Button, Card, Result, Statistic, Typography } from "antd";

import { Icon, StatusTag } from "./UI";

export function SummaryScreen({ summary, onStartReview, onBackToSetup }) {
  if (!summary?.counts) return null;
  const { compared_pairs, folders, review_clusters, safe_clusters } = summary.counts;
  const summaryStats = [
    {
      key: "safe",
      title: "בטוח למחיקה",
      value: safe_clusters,
      icon: "shield",
      copy: "קבוצות שהמערכת סיווגה כבטוחות יחסית לפעולה.",
    },
    {
      key: "review",
      title: "דורש בדיקה",
      value: review_clusters,
      icon: "alert",
      copy: "קבוצות שדורשות החלטה ידנית לפני כל מחיקה.",
    },
    {
      key: "pairs",
      title: "זוגות שנבדקו",
      value: compared_pairs ?? 0,
      icon: "compare",
      copy: `${folders ?? 0} תיקיות השתתפו בניתוח הנוכחי.`,
    },
  ];

  return (
    <div className="screen-center">
      <div className="summary-shell">
        <Result
          className="cartoon-card"
          icon={<Icon name="check-circle" size={68} />}
          title={<Typography.Title level={1}>הסריקה הושלמה!</Typography.Title>}
          subTitle={(
            <Typography.Paragraph style={{ margin: 0 }}>
              המודל המתמטי ומנוע ה-AI סיימו לנתח את הקבצים. במסך הבא תוכל לראות גם את פירוק הציונים בצורה מלאה יותר.
            </Typography.Paragraph>
          )}
          extra={(
            <div className="screen-actions">
              <Button type="default" size="large" icon={<Icon name="arrow-left" size={16} />} onClick={onBackToSetup}>
                סריקה חדשה
              </Button>
              <Button type="primary" size="large" icon={<Icon name="compare" size={16} />} onClick={onStartReview}>
                התחל לעבור על התוצאות
              </Button>
            </div>
          )}
        >
          <div className="summary-topline">
            <StatusTag tone="success" icon="shield">
              מוכן למעבר על התוצאות
            </StatusTag>
            <Typography.Text type="secondary">
              כל ההחלטות עדיין הפיכות לפני שלב ההעברה.
            </Typography.Text>
          </div>

          <div className="summary-stats" data-testid="summary-stats">
            {summaryStats.map((item) => (
              <Card key={item.key} className="summary-stat-card cartoon-panel" variant="borderless">
                <Statistic title={item.title} value={item.value} prefix={<Icon name={item.icon} size={18} />} />
                <div className="muted-copy">{item.copy}</div>
              </Card>
            ))}
          </div>

          <Alert
            className="summary-note"
            type="info"
            showIcon
            icon={<Icon name="info" size={16} />}
            title="שום קובץ לא יועבר עדיין. במסך הסקירה תוכל לאשר כל החלטה ידנית."
          />
        </Result>
      </div>
    </div>
  );
}
