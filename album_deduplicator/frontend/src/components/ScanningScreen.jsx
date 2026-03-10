import React from "react";

export function ScanningScreen({ progress }) {
  const percent = Math.round(progress.percent || 0);

  return (
    <div className="modal-backdrop">
      <div className="native-dialog" style={{ width: 400 }}>
        <div className="native-dialog-header">
          <h1>סריקה בתהליך</h1>
          <p>מנועי ההשוואה מנתחים את הקבצים</p>
        </div>
        
        <div className="native-dialog-body">
          <div className="scan-progress-area">
            <div style={{ fontWeight: 600, fontSize: 13 }}>{progress.message}</div>
            <div className="scan-progress-bar">
              <div className="scan-progress-fill" style={{ width: `${percent}%` }}></div>
            </div>
            <div className="scan-status-text">{progress.human_message} ({percent}%)</div>
          </div>
        </div>
      </div>
    </div>
  );
}