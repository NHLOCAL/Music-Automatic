import React from "react";
import { Progress, Tag } from "antd";

const stageLabels = {
  queued: "ממתין",
  scanning: "סורק תיקיות",
  compare: "משווה אלבומים",
  clustering: "בונה קבוצות",
  complete: "הושלם",
};

export function ScanningScreen({ progress }) {
  const percent = Math.round(progress.percent || 0);
  const current = progress.current ?? 0;
  const total = progress.total ?? 0;
  const stageLabel = stageLabels[progress.stage] ?? "ניתוח פעיל";

  return (
    <div className="modal-backdrop">
      <div className="native-dialog" style={{ width: 400 }}>
        <div className="native-dialog-header">
          <div className="dialog-banner-strip">
            <Tag bordered={false} className="dialog-banner-chip">סריקה פעילה</Tag>
            <Tag bordered={false} className="dialog-banner-chip dialog-banner-chip--accent">{stageLabel}</Tag>
          </div>
          <h1>סריקה בתהליך</h1>
          <p>מנועי ההשוואה מנתחים את הקבצים</p>
        </div>
        
        <div className="native-dialog-body">
          <div className="scan-progress-area scan-progress-area--elevated">
            <div className="scan-progress-header">
              <div style={{ fontWeight: 600, fontSize: 13, textAlign: "right" }}>{progress.message || "ממתין"}</div>
              <Tag bordered={false} className="dialog-banner-chip">{percent}%</Tag>
            </div>
            <Progress percent={percent} showInfo={false} />
            <div className="scan-status-text">{progress.human_message} ({percent}%)</div>
            <div className="scan-progress-summary">
              <div className="scan-progress-stat">
                <span>פריטים שעובדו</span>
                <strong>{total > 0 ? `${current}/${total}` : "ממתין לנתונים"}</strong>
              </div>
              <div className="scan-progress-stat">
                <span>סטטוס</span>
                <strong>{percent >= 100 ? "הסריקה הושלמה" : stageLabel}</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
