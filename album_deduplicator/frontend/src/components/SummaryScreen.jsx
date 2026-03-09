import React from "react";
import { Alert, Button, Card, Col, Result, Row, Statistic, Typography } from "antd";

import { Icon, StatusTag } from "./UI";

export function SummaryScreen({ summary, onStartReview, onBackToSetup }) {
  if (!summary?.counts) return null;
  const { safe_clusters, review_clusters } = summary.counts;

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
          <StatusTag tone="success" icon="shield">
            מוכן למעבר על התוצאות
          </StatusTag>

          <Row gutter={[16, 16]} className="summary-stats">
            <Col xs={24} md={12}>
              <Card className="summary-stat-card cartoon-panel" variant="borderless">
                <Statistic title="בטוח למחיקה" value={safe_clusters} prefix={<Icon name="shield" size={18} />} />
                <div className="muted-copy">עותקים בטוחים למחיקה</div>
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card className="summary-stat-card cartoon-panel" variant="borderless">
                <Statistic title="דורש בדיקה" value={review_clusters} prefix={<Icon name="alert" size={18} />} />
                <div className="muted-copy">דורשים סקירה</div>
              </Card>
            </Col>
          </Row>

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
