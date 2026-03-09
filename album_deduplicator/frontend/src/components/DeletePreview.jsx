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

  return (
    <Card className="delete-preview-card cartoon-card" variant="borderless">
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
            <Typography.Paragraph style={{ margin: "4px 0 0" }}>
              {workflowSummary.pendingCount > 0
                ? `ממתינות ${workflowSummary.pendingCount} תיקיות להעברה • ${formatSizeMb(workflowSummary.pendingSizeMb)}`
                : "אין כרגע פריטים חדשים שממתינים להעברה"}
            </Typography.Paragraph>
            <Typography.Text type="secondary">
              {workflowSummary.deletedCount > 0
                ? `${workflowSummary.deletedCount} כבר הועברו`
                : "עדיין לא בוצעה העברה מתוך הזרימה המרוכזת"}
              {workflowSummary.failedCount > 0 ? ` • ${workflowSummary.failedCount} דורשות טיפול` : ""}
            </Typography.Text>
          </div>
        </div>

        <Space className="delete-preview-stats" wrap size={8}>
          <StatusTag tone={workflowSummary.pendingCount > 0 ? "warning" : "neutral"} icon="trash">
            {workflowSummary.pendingCount} ממתינות
          </StatusTag>
          {workflowSummary.deletedCount > 0 ? (
            <StatusTag tone="success" icon="check-circle">
              {workflowSummary.deletedCount} הועברו
            </StatusTag>
          ) : null}
          {workflowSummary.failedCount > 0 ? (
            <StatusTag tone="danger" icon="alert">
              {workflowSummary.failedCount} דורשות טיפול
            </StatusTag>
          ) : null}
        </Space>

        <Button
          size="large"
          type="primary"
          danger
          icon={<Icon name="trash" size={16} />}
          onClick={onOpenFinalize}
          disabled={isExecuting}
        >
          פתח את שלב ההעברה
        </Button>
      </div>
    </Card>
  );
}
