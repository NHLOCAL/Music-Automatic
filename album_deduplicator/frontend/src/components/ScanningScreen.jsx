import React from "react";

export function ScanningScreen({ progress }) {
  const percent = Math.round(progress.percent || 0);
  const offset = 440 - (440 * percent) / 100; // 2 * PI * 70 approx 440

  return (
    <div className="centered-view">
      <div className="scanning-wrapper">
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
      </div>
    </div>
  );
}