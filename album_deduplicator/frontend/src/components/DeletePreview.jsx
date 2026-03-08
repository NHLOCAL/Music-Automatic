import React from "react";
import { Button, Icon } from "./UI";
import { formatSizeMb } from "../utils";

export function DeletePreview({ workflowSummary, onOpenFinalize, isExecuting }) {
  if (!workflowSummary || (workflowSummary.pendingCount === 0 && workflowSummary.deletedCount === 0 && workflowSummary.failedCount === 0)) {
    return null;
  }

  return (
    <div className="fab-container">
      <div className="fab-info">
        <div className="fab-badge">
          <Icon name="trash" size={14} />
          {workflowSummary.pendingCount}
        </div>
        <div>
          <div className="fab-title">שלב ההעברה הסופי מוכן</div>
          <div className="fab-copy">
            {workflowSummary.pendingCount > 0
              ? `ממתינות ${workflowSummary.pendingCount} תיקיות להעברה • ${formatSizeMb(workflowSummary.pendingSizeMb)}`
              : "אין כרגע פריטים חדשים שממתינים להעברה"}
          </div>
          <div className="fab-subcopy">
            {workflowSummary.deletedCount > 0
              ? `${workflowSummary.deletedCount} כבר הועברו`
              : "עדיין לא בוצעה העברה מתוך הזרימה המרוכזת"}
            {workflowSummary.failedCount > 0 ? ` • ${workflowSummary.failedCount} דורשות טיפול` : ""}
          </div>
        </div>
      </div>
      
      <Button variant="danger" size="lg" onClick={onOpenFinalize} disabled={isExecuting}>
        <Icon name="trash" size={16} />
        פתח את שלב ההעברה
      </Button>
    </div>
  );
}
