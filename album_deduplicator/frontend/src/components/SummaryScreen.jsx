import React from "react";
import { Button } from "antd";
import { Icon } from "./UI";

export function SummaryScreen({ summary, onStartReview }) {
  const { safe_clusters, review_clusters, compared_pairs } = summary.counts;

  return (
    <div className="modal-backdrop">
      <div className="native-dialog" style={{ width: 400 }}>
        <div className="native-dialog-header" style={{ borderBottomColor: '#4ac26b' }}>
          <h1 style={{ color: '#1a7f37' }}>הסריקה הושלמה בהצלחה</h1>
          <p>המידע מוכן למעבר</p>
        </div>
        
        <div className="native-dialog-body">
          <div className="summary-stats-row">
            <div className="summary-stat">
              <span className="val">{safe_clusters}</span>
              <span className="lbl">בטוחים למחיקה</span>
            </div>
            <div className="summary-stat">
              <span className="val">{review_clusters}</span>
              <span className="lbl">דורשים סקירה</span>
            </div>
            <div className="summary-stat">
              <span className="val">{compared_pairs}</span>
              <span className="lbl">זוגות שהושוו</span>
            </div>
          </div>
        </div>

        <div className="native-dialog-footer">
          <div style={{ display: "flex", gap: 10, width: "100%" }}>
            <Button type="primary" icon={<Icon name="eye" size={14} />} onClick={onStartReview} style={{ flex: 1 }}>
              פתח סביבת עבודה
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
