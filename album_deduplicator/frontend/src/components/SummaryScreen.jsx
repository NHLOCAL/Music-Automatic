import React from "react";
import { Badge, Button, Icon } from "./UI";

export function SummaryScreen({ summary, onStartReview, onBackToSetup }) {
  if (!summary?.counts) return null;
  const { safe_clusters, review_clusters } = summary.counts;
  
  return (
    <div className="centered-view">
      <div className="summary-container">
        <div className="success-icon">
          <Icon name="check-circle" size={40} />
        </div>
        
        <Badge tone="success" icon="shield">מוכן למעבר על התוצאות</Badge>
        <h1 className="summary-title">הסריקה הושלמה!</h1>
        <p className="summary-description">
           המודל המתמטי ומנוע ה-AI סיימו לנתח את הקבצים. במסך הבא תוכל לראות גם את פירוק הציונים בצורה מלאה יותר.
        </p>

        <div className="summary-stats-grid">
          <div className="stat-card highlight">
            <div className="stat-card-head">
              <Icon name="shield" size={16} />
              בטוח למחיקה
            </div>
            <div className="stat-value">{safe_clusters}</div>
            <div className="stat-label">עותקים בטוחים למחיקה</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-head warning">
              <Icon name="alert" size={16} />
              דורש בדיקה
            </div>
            <div className="stat-value stat-value-warning">{review_clusters}</div>
            <div className="stat-label">דורשים סקירה</div>
          </div>
        </div>

        <div className="summary-note">
          <Icon name="info" size={16} />
          שום קובץ לא יועבר עדיין. במסך הסקירה תוכל לאשר כל החלטה ידנית.
        </div>

        <div className="summary-actions">
          <Button variant="secondary" size="lg" className="summary-action-button" onClick={onBackToSetup}>
            <Icon name="arrow-left" size={16} />
            סריקה חדשה
          </Button>
          <Button variant="primary" size="lg" className="summary-action-button is-primary" onClick={onStartReview}>
            <Icon name="compare" size={16} />
            התחל לעבור על התוצאות
          </Button>
        </div>
      </div>
    </div>
  );
}
