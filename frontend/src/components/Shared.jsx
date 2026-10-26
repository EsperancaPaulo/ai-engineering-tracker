import React, {useEffect, useRef} from 'react';

export const roleLabels = {owner: 'Owner', editor: 'Editor', viewer: 'View only'};
export const statusLabels = {todo: 'To do', in_progress: 'In progress', done: 'Done'};
export function Brand({sidebar = false}) {
  return <a className="brand" href="/" aria-label="AI Engineering Tracker home"><span className="brand-mark">a<span>i</span></span>{sidebar ? <span>ENGINEERING<br/>TRACKER</span> : 'ENGINEERING TRACKER'}</a>;
}
export function ErrorMessage({message, id}) {return message ? <p id={id} className="error" role="alert">{message}</p> : null;}
export function EmptyState({title, children}) {return <div className="empty-state"><strong>{title}</strong><p>{children}</p></div>;}
export function Action({children, label, onClick, disabled = false}) {
  return <button type="button" className={`item-action ${children === 'Delete' ? 'delete-action' : ''}`} aria-label={label} onClick={onClick} disabled={disabled}>{children}</button>;
}
export function SectionHeading({eyebrow, title, children}) {
  return <div className="section-heading"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div>{children}</div>;
}
export function Modal({title, titleId, children, onClose, closeLabel = 'Close dialog'}) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog.open) dialog.showModal();
    dialog.querySelector('[data-initial-focus]')?.focus();
    return () => {if (dialog.open) dialog.close();};
  }, []);
  return <dialog ref={ref} aria-labelledby={titleId} onCancel={event => {event.preventDefault(); onClose();}}>
    <div className="dialog-heading"><h2 id={titleId}>{title}</h2><button type="button" aria-label={closeLabel} onClick={onClose}>×</button></div>{children}
  </dialog>;
}
export function activitySummary(details) {
  if (!details) return '';
  try {const value = JSON.parse(details); return typeof value.summary === 'string' ? value.summary : details;} catch {return details;}
}
