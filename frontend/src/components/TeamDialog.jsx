import React, {useCallback, useEffect, useState} from 'react';
import {jsonOptions} from '../api.js';
import {Action, ErrorMessage, Modal, roleLabels} from './Shared.jsx';

export default function TeamDialog({project, user, api, onClose, onSaved}) {
  const [members, setMembers] = useState([]), [loading, setLoading] = useState(true);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [removing, setRemoving] = useState(null);
  const [email, setEmail] = useState(''), [role, setRole] = useState('editor');
  const load = useCallback(async signal => {
    const values = await api(`/api/projects/${project.id}/members`, {signal});
    if (!signal?.aborted) setMembers(values);
  }, [api, project.id]);
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).catch(error => {if (!controller.signal.aborted) setError(error.message);}).finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [load]);
  async function mutate(path, options, message) {
    setBusy(true); setError('');
    try {await api(path, options); await load(); setRemoving(null); await onSaved(message); return true;}
    catch(error) {setError(error.message); return false;} finally {setBusy(false);}
  }
  async function add(event) {
    event.preventDefault();
    if (await mutate(`/api/projects/${project.id}/members`, jsonOptions({email: email.trim(), role}), 'Member added to project.')) {setEmail(''); setRole('editor');}
  }
  return <Modal title="Project team" titleId="team-title" onClose={onClose} closeLabel="Close project team">
    <p className="subtle">{project.name}</p><p className="field-hint">Owners manage access and assignments. Editors contribute tasks. Viewers have read-only access.</p>
    <div className="team-members" aria-busy={loading}>{loading ? <p className="subtle">Loading members…</p> : members.map(member => <div className="member-row" key={member.user_id}>
      <strong>{member.name}{member.user_id === user.id ? ' (you)' : ''}</strong>
      {project.role === 'owner' && member.role !== 'owner' ? <>
        <select aria-label={`Role for ${member.name}`} disabled={busy} value={member.role} onChange={e => mutate(`/api/projects/${project.id}/members/${member.user_id}`, jsonOptions({role: e.target.value}, 'PUT'), 'Project role updated.')}><option value="editor">Editor</option><option value="viewer">View only</option></select>
        <Action label={`Remove ${member.name} from project`} disabled={busy} onClick={() => setRemoving(member)}>Remove</Action>
      </> : <span className="tag">{roleLabels[member.role]}</span>}
    </div>)}</div>
    {removing && <div className="member-removal" role="group" aria-label="Confirm member removal"><p>Remove {removing.name}? Their project access will end immediately. You can add them again later.</p><div className="delete-buttons"><button type="button" className="secondary" disabled={busy} onClick={() => setRemoving(null)}>Keep member</button><button type="button" className="danger" disabled={busy} onClick={() => mutate(`/api/projects/${project.id}/members/${removing.user_id}`, {method: 'DELETE'}, 'Member removed.')}>Remove member</button></div></div>}
    <ErrorMessage message={error}/>
    {project.role === 'owner' && <form id="member-form" onSubmit={add}><h3>Add a registered member</h3><label htmlFor="member-email">Email address</label><input id="member-email" type="email" value={email} onChange={e => setEmail(e.target.value)} required maxLength={255} autoComplete="off" disabled={busy}/><label htmlFor="member-role">Project role</label><select id="member-role" value={role} onChange={e => setRole(e.target.value)} disabled={busy}><option value="editor">Editor — contribute work</option><option value="viewer">Viewer — read only</option></select><p className="field-hint">Access is granted immediately. This person must already have an account. No invitation email is sent.</p><button type="submit" className="primary" disabled={busy || loading}>{busy ? 'Saving…' : 'Add to project'}</button></form>}
  </Modal>;
}
