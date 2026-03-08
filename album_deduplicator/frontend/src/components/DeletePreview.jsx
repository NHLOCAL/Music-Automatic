import React from "react";
import { Button } from "./UI";
import { formatSizeMb } from "../utils";

export function DeletePreview({ workflowSummary, onOpenFinalize, isExecuting }) {
  if (!workflowSummary || (workflowSummary.pendingCount === 0 && workflowSummary.deletedCount === 0 && workflowSummary.failedCount === 0)) {
    return null;
  }

  return (
    <div className="fab-container">
      <div className="fab-info">
        <div className="fab-badge">{workflowSummary.pendingCount}</div>
        <div>
          <div style={{ fontWeight: 600, fontSize: "1rem" }}>שלב ההעברה הסופי מוכן</div>
          <div style={{ fontSize: "0.85rem", opacity: 0.9 }}>
            {workflowSummary.pendingCount > 0
              ? `ממתינות ${workflowSummary.pendingCount} תיקיות להעברה • ${formatSizeMb(workflowSummary.pendingSizeMb)}`
              : "אין כרגע פריטים חדשים שממתינים להעברה"}
          </div>
          <div style={{ fontSize: "0.8rem", opacity: 0.72, marginTop: "2px" }}>
            {workflowSummary.deletedCount > 0
              ? `${workflowSummary.deletedCount} כבר הועברו`
              : "עדיין לא בוצעה העברה מתוך הזרימה המרוכזת"}
            {workflowSummary.failedCount > 0 ? ` • ${workflowSummary.failedCount} דורשות טיפול` : ""}
          </div>
        </div>
      </div>
      
      <Button variant="danger" size="lg" onClick={onOpenFinalize} disabled={isExecuting}>
        פתח את שלב ההעברה
      </Button>
    </div>
  );
}
