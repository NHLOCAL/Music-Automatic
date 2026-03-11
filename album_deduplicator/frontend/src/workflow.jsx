import React from "react";

import { getScanProgressModel } from "./scanProgress";

export const WORKFLOW_STEP_KEYS = ["setup", "scanning", "summary", "review", "finalize"];

function buildCountBadge(text, tone = "neutral", stepKey) {
  if (!text) return null;
  return (
    <span
      key={stepKey}
      className={`workflow-rail-badge workflow-rail-badge--${tone}`}
      data-testid={`workflow-step-badge-${stepKey}`}
    >
      {text}
    </span>
  );
}

export function getWorkflowStepIndex(stepKey) {
  const index = WORKFLOW_STEP_KEYS.indexOf(stepKey);
  return index === -1 ? 0 : index;
}

export function getWorkflowStepState({ appView, status, summary, preview, progress }) {
  const hasSummary = Boolean(summary);
  const isCompleted = status === "completed" && hasSummary;
  const isRunning = status === "running";
  const isFailed = status === "failed";
  const safeCount = summary?.counts?.safe_clusters ?? 0;
  const reviewCount = summary?.counts?.review_clusters ?? 0;
  const pendingCount = preview?.total_count ?? 0;
  const scanProgress = getScanProgressModel(progress);

  return [
    {
      key: "setup",
      title: "בחירה",
      enabled: status === "idle" || isFailed || isCompleted,
      active: appView === "setup",
      description: isCompleted
        ? "אפשר לעדכן תיקיות בלי לאבד את התוצאות האחרונות"
        : isFailed
          ? "עדכנו את הבחירה והפעילו שוב"
          : "בחרו תיקיות, העדפה והגדרות סריקה",
      badges: [],
    },
    {
      key: "scanning",
      title: "סריקה",
      enabled: isRunning,
      active: appView === "scanning",
      description: isRunning ? scanProgress.stageLabel : "יהפוך לזמין בזמן ניתוח פעיל",
      badges: [buildCountBadge(isRunning ? `${scanProgress.overallPercent}%` : null, "primary", "scanning")].filter(Boolean),
    },
    {
      key: "summary",
      title: "סיכום",
      enabled: hasSummary,
      active: appView === "summary",
      description: hasSummary ? "מבט מהיר על תוצאות הניתוח לפני העבודה הידנית" : "יופיע לאחר השלמת הסריקה",
      badges: [
        buildCountBadge(hasSummary ? `${safeCount} בטוחות` : null, "success", "summary-safe"),
        buildCountBadge(hasSummary ? `${reviewCount} לסקירה` : null, "warning", "summary-review"),
      ].filter(Boolean),
    },
    {
      key: "review",
      title: "סקירה",
      enabled: isCompleted,
      active: appView === "review",
      description: isCompleted ? "בדיקה ידנית, בחירת keeper וניהול סימוני מחיקה" : "ייפתח לאחר שהניתוח יושלם",
      badges: [],
    },
    {
      key: "finalize",
      title: "העברה",
      enabled: isCompleted,
      active: appView === "finalize",
      description: isCompleted ? "אימות אחרון לפני העברה לסל המחזור" : "ייפתח לאחר השלמת הניתוח",
      badges: [buildCountBadge(isCompleted ? `${pendingCount} למחיקה` : null, pendingCount > 0 ? "danger" : "neutral", "finalize")].filter(Boolean),
    },
  ];
}
