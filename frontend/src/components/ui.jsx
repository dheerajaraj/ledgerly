export function StatusPill({ status }) {
  const labels = { draft: "Draft", open: "Awaiting payment", paid: "Paid", expired: "Link expired", void: "Voided" };
  return <span className={`pill pill-${status}`}>{labels[status] ?? status}</span>;
}

export function ErrorNote({ error }) {
  if (!error) return null;
  return <p className="error" role="alert">{error}</p>;
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      <p className="empty-title">{title}</p>
      {children}
    </div>
  );
}
