import React from "react";
import { Button } from "./UI";
import { formatSizeMb } from "../utils";

export function DeletePreview({ preview, onConfirm, isExecuting }) {
  if (preview.total_count === 0) return null;

  const previewItems = preview.items.slice(0, 3);
  const hiddenCount = preview.items.length - previewItems.length;

  return (
    <div className="bottom-preview-bar">
      <div className="preview-content">
        <div className="preview-info">
          <div className="delete-count-circle">{preview.total_count}</div>
          <div className="preview-text">
            <h4>מוכנים להעברה לסל המחזור</h4>
            <p>
              {`המערכת סימנה ${preview.auto_selected_count} אוטומטית ועוד ${preview.manual_selected_count} ידנית. יתפנו כ-${formatSizeMb(preview.total_size_mb)}.`}
            </p>
            <div className="preview-folder-list">
              {previewItems.map((item) => (
                <span key={item.folder_id} className="preview-folder-chip">
                  {item.folder_name}
                </span>
              ))}
              {hiddenCount > 0 && <span className="preview-folder-chip muted">+{hiddenCount} נוספים</span>}
            </div>
          </div>
        </div>
        <Button variant="danger" className="execute-btn" onClick={onConfirm} disabled={isExecuting}>
          {isExecuting ? "מעביר..." : "העבר לסל המחזור"}
        </Button>
      </div>
    </div>
  );
}
