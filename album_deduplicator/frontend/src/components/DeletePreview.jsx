import React from "react";
import { Button, Card, Space, Typography } from "antd";

import { Icon, StatusTag } from "./UI";
import { formatSizeMb } from "../utils";

export function DeletePreview({ workflowSummary, onOpenFinalize, isExecuting }) {
  if (
    !workflowSummary
    || (workflowSummary.pendingCount === 0
      && workflowSummary.deletedCount === 0
      && workflowSummary.failedCount === 0)
  ) {
    return null;
  }

  const hasPending = workflowSummary.pendingCount > 0;
  const hasFailures = workflowSummary.failedCount > 0;
  const primaryActionLabel = hasPending ? "עבור לשלב ההעברה" : "פתח היסטוריית העברות";
  const summaryLine = hasPending
    ? `ממתינות ${workflowSummary.pendingCount} תיקיות להעברה • ${formatSizeMb(workflowSummary.pendingSizeMb)}`
    : "אין כרגע פריטים חדשים שממתינים להעברה";
  const statusLine = workflowSummary.deletedCount > 0
    ? `${workflowSummary.deletedCount} כבר הועברו מתוך הזרימה המרוכזת`
    : "עדיין לא בוצעה העברה מתוך הזרימה המרוכזת";

  return (
    <Card className="delete-preview-card cartoon-card" variant="borderless" role="region" aria-label="שלב ההעברה הסופי מוכן">
      <div className="delete-preview-body">
        <div className="delete-preview-copy">
          <div className="soft-kicker">
            <Icon name="trash" size={14} />
            מוכנות להעברה
          </div>
          <div className="delete-preview-text">
            <Typography.Title level={4} style={{ margin: 0 }}>
              שלב ההעברה הסופי מוכן
            </Typography.Title>
            <Typography.Paragraph className="delete-preview-summary">
              {summaryLine}
            </Typography.Paragraph>
            <Typography.Text type="secondary" className="delete-preview-secondary">
              {statusLine}
              {hasFailures ? ` • ${workflowSummary.failedCount} דורשות טיפול לפני ניסיון נוסף` : ""}
            </Typography.Text>
          </div>
          <div className="delete-preview-trust">
            <Icon name="shield" size={14} />
            <span>המעבר הבא ישלח רק את הפריטים שנבחרו לסל המחזור, בלי מחיקה לצמיתות.</span>
          </div>
        </div>

        <div className="delete-preview-stat-grid">
          <div className="delete-preview-stat-card is-pending">
            <Typography.Text type="secondary">ממתינות עכשיו</Typography.Text>
            <Typography.Title level={3}>{workflowSummary.pendingCount}</Typography.Title>
            <Typography.Text>{formatSizeMb(workflowSummary.pendingSizeMb)}</Typography.Text>
          </div>
          <div className="delete-preview-stat-card is-history">
            <Typography.Text type="secondary">כבר הועברו</Typography.Text>
            <Typography.Title level={3}>{workflowSummary.deletedCount}</Typography.Title>
            <Typography.Text>{hasPending ? "מוכנות לסבב הבא" : "היסטוריה זמינה לעיון"}</Typography.Text>
          </div>
          <div className={`delete-preview-stat-card ${hasFailures ? "is-attention" : "is-calm"}`}>
            <Typography.Text type="secondary">מצב טיפול</Typography.Text>
            <Typography.Title level={3}>{workflowSummary.failedCount}</Typography.Title>
            <Typography.Text>{hasFailures ? "דורשות בדיקה" : "אין כשלים פתוחים"}</Typography.Text>
          </div>
        </div>

        <div className="delete-preview-actions">
          <Space className="delete-preview-stats" wrap size={8}>
            <StatusTag tone={hasPending ? "warning" : "neutral"} icon="trash">
            {workflowSummary.pendingCount} ממתינות
            </StatusTag>
            {workflowSummary.deletedCount > 0 ? (
              <StatusTag tone="success" icon="check-circle">
                {workflowSummary.deletedCount} הועברו
              </StatusTag>
            ) : null}
            {hasFailures ? (
              <StatusTag tone="danger" icon="alert">
                {workflowSummary.failedCount} דורשות טיפול
              </StatusTag>
            ) : null}
          </Space>

          <Button
            size="large"
            type={hasPending || hasFailures ? "primary" : "default"}
            icon={<Icon name={hasFailures ? "alert" : hasPending ? "compare" : "eye"} size={16} />}
            onClick={onOpenFinalize}
            disabled={isExecuting}
          >
            {primaryActionLabel}
          </Button>

          <Typography.Text type="secondary" className="delete-preview-action-hint">
            {hasFailures
              ? "פתח את המרכז כדי לראות אילו פריטים דורשים טיפול ואילו כבר מוכנים לאישור."
              : hasPending
                ? "במרכז ההעברה תראה כל תיקייה מול ה-keeper שנשמר לפני אישור."
                : "אפשר לפתוח את המרכז כדי לעיין במה שכבר הועבר ובמה שנשמר."}
          </Typography.Text>
        </div>
      </div>
    </Card>
  );
}
