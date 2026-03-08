import React from "react";
import { Button } from "./UI";
import { formatSizeMb } from "../utils";
export function DeletePreview({ preview, onConfirm, isExecuting }) {
  if (preview.total_count === 0) return null;
  return (
    <div className="bottom-preview-bar">
      <div className="preview-content">
        <div className="preview-info">
          <div className="delete-count-circle">{preview.total_count}</div>
          <div className="preview-text">
            <h4>מוכנים להעברה לסל המחזור</h4>
            <p>שום קובץ לא יימחק לצמיתות. המערכת תפנה כ-{formatSizeMb(preview.total_size_mb)}.</p>
          </div>
        </div>
        <Button variant="danger" className="execute-btn" onClick={onConfirm} disabled={isExecuting}>
          {isExecuting ? "מעביר..." : "העבר לסל המחזור"}
        </Button>
      </div>
    </div>
  );
}