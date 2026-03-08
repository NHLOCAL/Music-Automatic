import React from "react";
import { Button } from "./UI";
import { formatSizeMb } from "../utils";

export function DeletePreview({ preview, onConfirm, isExecuting }) {
  if (preview.total_count === 0) return null;
  
  return (
    <div className="floating-action-bar">
      <div className="fab-info">
        <div className="fab-count">{preview.total_count}</div>
        <div className="fab-text">
          <h4>מוכנים להעברה לסל המחזור</h4>
          <p>יתפנו כ-{formatSizeMb(preview.total_size_mb)} במצטבר</p>
        </div>
      </div>
      <Button variant="danger" onClick={onConfirm} disabled={isExecuting}>
        {isExecuting ? "מעביר לסל..." : "העבר לסל (Enter)"}
      </Button>
    </div>
  );
}