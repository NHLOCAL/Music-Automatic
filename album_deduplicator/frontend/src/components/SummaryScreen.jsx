import React from "react";
import { Button } from "./UI";

export function SummaryScreen({ summary, onStartReview }) {
  if (!summary?.counts) return null;

  const { safe_clusters, review_clusters } = summary.counts;
  const total = safe_clusters + review_clusters;

  return (
    <div className="centered-view">
      <div className="summary-card">
        <div className="icon-hero" style={{ color: 'var(--accent-success)', background: 'var(--accent-success-bg)' }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
          </svg>
        </div>
        <h1>הסריקה הושלמה בהצלחה</h1>
        <p>נמצאו סך הכל {total} קבוצות של אלבומים כפולים.</p>
        
        <div className="summary-stats">
          <div className="stat-box success">
            <div className="stat-number">{safe_clusters}</div>
            <div className="stat-label">בטוחים למחיקה</div>
          </div>
          <div className="stat-box warning">
            <div className="stat-number">{review_clusters}</div>
            <div className="stat-label">דורשים סקירה</div>
          </div>
        </div>

        <Button variant="primary" size="lg" style={{ width: '100%' }} onClick={onStartReview}>
          התחל לעבור על התוצאות
        </Button>
      </div>
    </div>
  );
}
