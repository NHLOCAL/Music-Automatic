import React from "react";
import { Button } from "./UI";
import { formatSizeMb } from "../utils";

export function DeletePreview({ preview, onConfirm, isExecuting }) {
  if (preview.total_count === 0) return null;
  
  return (
    <div className="fab-container">
      <div className="fab-info">
        <div className="fab-badge">{preview.total_count}</div>
        <div>
           <div style={{ fontWeight: 600, fontSize: '1rem' }}>מוכנים להעברה לסל המחזור</div>
           <div style={{ fontSize: '0.85rem', opacity: 0.9 }}>חיסכון צפוי: {formatSizeMb(preview.total_size_mb)}</div>
        </div>
      </div>
      
      <Button variant="danger" size="lg" onClick={onConfirm} disabled={isExecuting}>
        {isExecuting ? "מבצע..." : "העבר לסל המחזור"}
      </Button>
    </div>
  );
}