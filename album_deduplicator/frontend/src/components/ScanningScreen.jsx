import React from "react";

export function ScanningScreen({ progress }) {
  const percent = Math.round(progress.percent || 0);
  const offset = 283 - (283 * percent) / 100;

  return (
    <div className="centered-view">
      <div className="scan-progress-container">
        <div className="circular-progress">
          <svg viewBox="0 0 100 100">
            <circle className="progress-bg" cx="50" cy="50" r="45" />
            <circle className="progress-value" cx="50" cy="50" r="45" strokeDasharray="283" strokeDashoffset={offset} />
          </svg>
          <div className="progress-text">{percent}%</div>
        </div>
        <h2>{progress.message}</h2>
        <p>{progress.human_message}</p>
      </div>
    </div>
  );
}