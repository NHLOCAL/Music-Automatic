import React from "react";
import { Icon } from "./UI";

export function ScanningScreen({ progress }) {
  const percent = Math.round(progress.percent || 0);
  const offset = 440 - (440 * percent) / 100; // 2 * PI * 70 approx 440
  const progressDetails = [
    {
      icon: "folder",
      label: "שלב פעיל",
      value: progress.stage || "scan",
    },
    {
      icon: "clock",
      label: "התקדמות",
      value: progress.total ? `${progress.current || 0}/${progress.total}` : `${percent}%`,
    },
    {
      icon: "shield",
      label: "מצב",
      value: percent >= 100 ? "מוכן לסקירה" : "מריץ ניתוח",
    },
  ];

  return (
    <div className="centered-view">
      <div className="scanning-wrapper">
        <div className="scanning-header-chip">
          <Icon name="sparkle" size={14} />
          סריקה חכמה בתהליך
        </div>
        <div className="progress-ring">
          <svg viewBox="0 0 160 160">
            <circle className="progress-ring-bg" cx="80" cy="80" r="70" />
            <circle 
              className="progress-ring-val" 
              cx="80" cy="80" r="70" 
              strokeDasharray="440" 
              strokeDashoffset={offset} 
            />
          </svg>
          <div className="progress-text">{percent}%</div>
        </div>
        
        <div className="scanning-info">
          <h2>{progress.message}</h2>
          <p>{progress.human_message}</p>
        </div>

        <div className="scan-status-grid">
          {progressDetails.map((item) => (
            <div key={item.label} className="scan-status-card">
              <span className="scan-status-icon">
                <Icon name={item.icon} size={15} />
              </span>
              <div>
                <div className="scan-status-label">{item.label}</div>
                <strong className="scan-status-value">{item.value}</strong>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
