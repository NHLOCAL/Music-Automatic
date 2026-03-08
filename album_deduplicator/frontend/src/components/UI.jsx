import React from "react";
export function Button({ variant = "primary", className = "", children, ...props }) {
  const baseClass = "btn";
  const variants = {
    primary: "btn-primary",
    secondary: "btn-secondary",
    danger: "btn-danger",
    ghost: "btn-ghost",
  };
  return (
    <button className={`${baseClass} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}
export function Badge({ tone = "neutral", children }) {
  const tones = {
    success: "badge-success",
    warning: "badge-warning",
    danger: "badge-danger",
    neutral: "badge-neutral",
  };
  return <span className={`badge ${tones[tone]}`}>{children}</span>;
}
export function ConfirmModal({ title, body, confirmText, onConfirm, onCancel, isDanger = false }) {
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-content">
        <h3 className="modal-title">{title}</h3>
        <p className="modal-body">{body}</p>
        <div className="modal-actions">
          <Button variant={isDanger ? "danger" : "primary"} onClick={onConfirm}>{confirmText}</Button>
          <Button variant="ghost" onClick={onCancel}>ביטול וחזרה</Button>
        </div>
      </div>
    </div>
  );
}