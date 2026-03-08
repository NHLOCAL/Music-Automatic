import React from "react";

export function Icon({ name, size = 18, className = "" }) {
  const icons = {
    trash: <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6" />,
    check: <polyline points="20 6 9 17 4 12" />,
    "check-circle": <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4L12 14.01l-3-3" />,
    folder: <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />,
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
    alert: <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01" />,
    music: <path d="M9 18V5l12-2v13M9 9l12-2M6 15a3 3 0 1 0 3 3v-3H6zm12-2a3 3 0 1 0 3 3v-3h-3z" />,
    eye: <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />,
    plus: <path d="M12 5v14M5 12h14" />,
    x: <path d="M18 6L6 18M6 6l12 12" />,
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82L4.21 7.2a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </>
    ),
    "chevron-down": <polyline points="6 9 12 15 18 9" />,
    sparkle: (
      <>
        <path d="M12 3l1.7 4.6L18 9.3l-4.3 1.7L12 15.6l-1.7-4.6L6 9.3l4.3-1.7L12 3z" />
        <path d="M19 4l.6 1.4L21 6l-1.4.6L19 8l-.6-1.4L17 6l1.4-.6L19 4z" />
        <path d="M5 15l.9 2.1L8 18l-2.1.9L5 21l-.9-2.1L2 18l2.1-.9L5 15z" />
      </>
    ),
    layers: (
      <>
        <path d="M12 3L2 8l10 5 10-5-10-5z" />
        <path d="M2 12l10 5 10-5" />
        <path d="M2 16l10 5 10-5" />
      </>
    ),
    compare: (
      <>
        <path d="M10 3H5a2 2 0 0 0-2 2v5" />
        <path d="M14 21h5a2 2 0 0 0 2-2v-5" />
        <path d="M21 10V5a2 2 0 0 0-2-2h-5" />
        <path d="M3 14v5a2 2 0 0 0 2 2h5" />
        <path d="M8 12h8" />
        <path d="M12 8l4 4-4 4" />
      </>
    ),
    chart: (
      <>
        <path d="M3 3v18h18" />
        <path d="M7 14l4-4 3 3 5-6" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 3" />
      </>
    ),
    database: (
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
        <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
      </>
    ),
    info: (
      <>
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4" />
        <path d="M12 8h.01" />
      </>
    ),
    "arrow-left": <path d="M19 12H5M12 19l-7-7 7-7" />
  };

  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {icons[name]}
    </svg>
  );
}

export function Button({ variant = "primary", size = "md", className = "", children, ...props }) {
  const sizeClass = size === "lg" ? "btn-lg" : size === "sm" ? "btn-sm" : size === "icon" ? "btn-icon" : "";
  const variantClass = `btn-${variant}`;
  return (
    <button className={`btn ${variantClass} ${sizeClass} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Badge({ tone = "neutral", icon, children }) {
  return (
    <span className={`badge badge-${tone}`}>
      {icon && <Icon name={icon} size={12} />}
      {children}
    </span>
  );
}

export function VisualMetric({ value, label, percent, tone = "primary" }) {
  const clampedPercent = Math.max(0, Math.min(100, percent));
  
  return (
    <div className="visual-metric">
      <div className="visual-metric-header">
        <span className="visual-metric-label">{label}</span>
        <span className="visual-metric-value">{value}</span>
      </div>
      <div className="visual-metric-bar-bg">
        <div 
          className={`visual-metric-bar-fill tone-${tone}`} 
          style={{ width: `${clampedPercent}%` }}
        />
      </div>
    </div>
  );
}

export function ConfirmModal({ title, body, confirmText, onConfirm, onCancel, isDanger = false }) {
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="modal-box">
        <h3 className="modal-title" style={{ color: isDanger ? 'var(--color-danger)' : 'var(--text-main)' }}>
           {title}
        </h3>
        <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{body}</p>
        <div className="modal-actions">
          <Button variant="secondary" onClick={onCancel}>ביטול</Button>
          <Button variant={isDanger ? "danger" : "primary"} onClick={onConfirm} autoFocus>{confirmText}</Button>
        </div>
      </div>
    </div>
  );
}
