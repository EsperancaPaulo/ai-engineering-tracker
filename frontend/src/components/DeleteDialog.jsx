import React, {useState} from 'react';
import {ErrorMessage, Modal} from './Shared.jsx';
export default function DeleteDialog({mode, item, api, onClose, onSaved}) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const isProject = mode === 'project';
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {await api(`/api/${isProject ? 'projects' : 'tasks'}/${item.id}`, {method:'DELETE'}); await onSaved(isProject ? 'Project deleted.' : 'Task deleted.'); onClose();}
    catch(error) {setError(error.message);} finally {setBusy(false);}
  }
  return <Modal title={isProject ? 'Delete project?' : 'Delete task?'} titleId="delete-title" onClose={onClose} closeLabel="Close deletion confirmation"><form onSubmit={submit}>
    <p className="delete-name">{isProject ? item.name : item.title}</p><p className="subtle">{isProject ? 'This removes the project for its members. Projects with any remaining tasks cannot be deleted. This action cannot be undone.' : 'This permanently removes this task and updates project progress. This action cannot be undone.'}</p><ErrorMessage message={error}/><div className="delete-buttons"><button className="secondary" type="button" onClick={onClose} disabled={busy} data-initial-focus="true">Keep it</button><button className="danger" type="submit" disabled={busy}>{busy ? 'Deleting…' : 'Delete permanently'}</button></div>
  </form></Modal>;
}
