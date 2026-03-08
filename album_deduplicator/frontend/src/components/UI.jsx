import React from "react";

export function Button({ variant = "primary", size = "md", className = "", children, ...props }) {
  const sizeClass = size === "lg" ? "btn-lg" : size === "sm" ? "btn-sm" : size === "icon" ? "btn-icon" : "";
  const variantClass = `btn-${variant}`;
  return (
    <button className={`btn ${variantClass} ${sizeClass} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Badge({ tone = "neutral", children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
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