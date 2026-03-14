import React from "react";
import { Progress, Tag } from "antd";

import { getScanProgressModel } from "../scanProgress";

export function ScanningScreen({ progress }) {
  const { overallPercent, stageLabel, strokeColor, railColor, chipColor, isComplete } = getScanProgressModel(progress);
  const current = progress.current ?? 0;
  const total = progress.total ?? 0;

  return (
    <div className="modal-backdrop">
      <div className="native-dialog" style={{ width: 400 }}>
        <div className="native-dialog-header">
          <div className="dialog-banner-strip">
            <Tag variant="filled" className="dialog-banner-chip">סריקה פעילה</Tag>
            <Tag
              variant="filled"
              className="dialog-banner-chip"
              style={{ backgroundColor: chipColor, borderColor: chipColor, color: "#fff" }}
            >
              {stageLabel}
            </Tag>
          </div>
          <h1>סריקה בתהליך</h1>
          <p>מנועי ההשוואה מנתחים את הקבצים</p>
        </div>
        
        <div className="native-dialog-body">
          <div className="scan-progress-area scan-progress-area--elevated">
            <div className="scan-progress-header">
              <div style={{ fontWeight: 600, fontSize: 13, textAlign: "right" }}>{progress.message || "ממתין"}</div>
              <Tag variant="filled" className="dialog-banner-chip">{overallPercent}%</Tag>
            </div>
            <Progress percent={overallPercent} showInfo={false} strokeColor={strokeColor} railColor={railColor} />
            <div className="scan-status-text">{progress.human_message}</div>
            <div className="scan-progress-note">
              האחוז הכולל משלב את כל שלבי הניתוח יחד: סריקה, איתור התאמות, חישוב איכות והשוואה.
            </div>
            <div className="scan-progress-summary">
              <div className="scan-progress-stat">
                <span>פריטים שעובדו</span>
                <strong>{total > 0 ? `${current}/${total}` : "ממתין לנתונים"}</strong>
              </div>
              <div className="scan-progress-stat">
                <span>סטטוס</span>
                <strong>{isComplete ? "הסריקה הושלמה" : stageLabel}</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
