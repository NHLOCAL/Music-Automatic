import React from "react";
import { Button } from "./UI";

export function SummaryScreen({ summary, onStartReview, onBackToSetup }) {
  if (!summary?.counts) return null;
  const { safe_clusters, review_clusters } = summary.counts;
  
  return (
    <div className="centered-view">
      <div className="summary-container">
        <div className="success-icon">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        
        <h1 style={{ fontSize: '2rem', marginBottom: '16px' }}>הסריקה הושלמה!</h1>
        <p style={{ fontSize: '1.1rem', color: 'var(--text-secondary)' }}>
           המודל המתמטי ומנוע ה-AI סיימו לנתח את הקבצים. במסך הבא תוכל לראות גם את פירוק הציונים בצורה מלאה יותר.
        </p>

        <div className="summary-stats-grid">
          <div className="stat-card highlight">
            <div className="stat-value">{safe_clusters}</div>
            <div className="stat-label">עותקים בטוחים למחיקה</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: 'var(--color-warning-text)' }}>{review_clusters}</div>
            <div className="stat-label">דורשים סקירה</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '16px' }}>
          <Button variant="secondary" size="lg" style={{ flex: 1 }} onClick={onBackToSetup}>
            סריקה חדשה
          </Button>
          <Button variant="primary" size="lg" style={{ flex: 2 }} onClick={onStartReview}>
            התחל לעבור על התוצאות
          </Button>
        </div>
      </div>
    </div>
  );
}
