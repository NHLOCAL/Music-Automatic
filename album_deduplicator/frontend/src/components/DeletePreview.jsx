import React from "react";
import { Button } from "./UI";
import { formatSizeMb } from "../utils";

export function DeletePreview({ preview, onConfirm, isExecuting }) {
  if (preview.total_count === 0) return null;

  return (
    <div className="bottom-bar">
      <div className="bottom-bar-info">
        <div className="delete-count">{preview.total_count}</div>
        <div className="bottom-bar-text">
          <h4>מוכנים להעברה לסל המחזור</h4>
          <p>יתפנו כ-{formatSizeMb(preview.total_size_mb)}.</p>
        </div>
      </div>
      <Button variant="danger" onClick={onConfirm} disabled={isExecuting}>
        {isExecuting ? "מוחק..." : "העבר לסל"} <kbd style={{ marginLeft: '8px', border: 'none', background: 'rgba(255,255,255,0.2)', color: 'white' }}>Enter</kbd>
      </Button>
    </div>
  );
}