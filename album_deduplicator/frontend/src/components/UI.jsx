import React from "react";

export function Button({ variant = "primary", size = "md", className = "", children, ...props }) {
  const baseClass = "btn";
  const sizeClass = size === "lg" ? "btn-lg" : size === "icon" ? "btn-icon" : "";
  const variantClass = `btn-${variant}`;
  
  return (
    <button className={`${baseClass} ${variantClass} ${sizeClass} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Badge({ tone = "neutral", children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function ConfirmModal({ title, body, confirmText, onConfirm, onCancel, isDanger = false }) {
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-content">
        <h3>{title}</h3>
        <p>{body}</p>
        <div className="modal-actions">
          <Button variant="ghost" onClick={onCancel}>ביטול</Button>
          <Button variant={isDanger ? "danger" : "primary"} onClick={onConfirm}>{confirmText}</Button>
        </div>
      </div>
    </div>
  );
}