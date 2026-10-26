import React, {useEffect, useState} from 'react';
import {jsonOptions} from '../api.js';
import {ErrorMessage, Modal} from './Shared.jsx';

export default function ItemDialog({mode, item, initialProjectId, projects, user, api, onClose, onSaved}) {
  const isProject = mode === 'project', editing = Boolean(item);
  const writable = projects.filter(project => project.role !== 'viewer');
  const [name, setName] = useState(item ? (isProject ? item.name : item.title) : '');
  const [description, setDescription] = useState(item?.description || '');
  const [priority, setPriority] = useState(item?.priority || 'medium');
  const [projectId, setProjectId] = useState(String(item?.project_id || initialProjectId || writable[0]?.id || ''));
  const [assignee, setAssignee] = useState(item?.assigned_to === null ? '' : String(item?.assigned_to || user.id));
  const [members, setMembers] = useState([]), [loading, setLoading] = useState(!isProject);
  const [memberError, setMemberError] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const project = projects.find(value => value.id === Number(projectId));
  const preserveUnassigned = editing && item.assigned_to === null && Number(projectId) === item.project_id;
  useEffect(() => {
    if (isProject || !projectId) return;
    let active = true; const controller = new AbortController();
    setLoading(true); setMemberError(''); setMembers([]);
    api(`/api/projects/${projectId}/members`, {signal: controller.signal}).then(values => {
      if (!active) return;
      const candidates = values.filter(member => member.role !== 'viewer' && (project.role === 'owner' || member.user_id === user.id));
      setMembers(candidates);
      setAssignee(current => candidates.some(member => String(member.user_id) === current) ? current : preserveUnassigned ? '' : '');
    }).catch(error => {if (active && error.name !== 'AbortError') setMemberError(error.message);}).finally(() => {if (active) setLoading(false);});
    return () => {active = false; controller.abort();};
  }, [api, isProject, projectId, project?.role, user.id, preserveUnassigned]);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const data = isProject ? {name: name.trim(), description: description.trim()} : {
      title: name.trim(), description: description.trim(), priority, project_id: Number(projectId),
      ...(assignee ? {assigned_to: Number(assignee)} : {}),
    };
    try {
      await api(`/api/${isProject ? 'projects' : 'tasks'}${editing ? `/${item.id}` : ''}`, jsonOptions(data, editing ? (isProject ? 'PUT' : 'PATCH') : 'POST'));
      await onSaved(editing ? 'Changes saved.' : isProject ? 'Project created. Let’s build something.' : 'Task added. You’ve got this.');
      onClose();
    } catch (error) {setError(error.message);} finally {setBusy(false);}
  }
  const title = editing ? (isProject ? 'Edit project' : 'Edit task') : isProject ? 'Give your idea a home.' : 'One small step forward.';
  return <Modal title={title} titleId="dialog-title" onClose={onClose}>
    <form id="create-form" onSubmit={submit}>
      <p className="subtle">{isProject ? editing ? 'These changes will be visible to members of this project.' : 'Only you can see this project until you add team members.' : editing ? 'Update your task details. Your current status will stay the same.' : 'Choose a project and the person responsible for this task.'}</p>
      <label htmlFor="item-name">{isProject ? 'Project name' : 'Task title'}</label><input id="item-name" value={name} onChange={e => setName(e.target.value)} maxLength={isProject ? 150 : 200} required data-initial-focus="true" disabled={busy}/>
      {isProject ? <><label htmlFor="description">Description <span className="subtle">(optional)</span></label><textarea id="description" value={description} onChange={e => setDescription(e.target.value)} rows={3} maxLength={4000} placeholder="What are you building?" disabled={busy}/></> : <>
        <label htmlFor="task-project">Project</label><select id="task-project" value={projectId} onChange={e => setProjectId(e.target.value)} required disabled={busy}>{writable.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
        <label htmlFor="task-priority">Priority</label><select id="task-priority" value={priority} onChange={e => setPriority(e.target.value)} disabled={busy}><option value="medium">Medium</option><option value="high">High</option><option value="low">Low</option></select>
        <label htmlFor="task-assignee">Assigned to</label><select id="task-assignee" value={assignee} onChange={e => setAssignee(e.target.value)} disabled={busy || loading || project?.role !== 'owner'} required={!preserveUnassigned}>
          <option value="">{loading ? 'Loading members…' : preserveUnassigned ? 'Unassigned (keep existing)' : 'Choose a project member'}</option>
          {members.map(member => <option key={member.user_id} value={member.user_id}>{member.name}{member.user_id === user.id ? ' (you)' : ''}</option>)}
        </select><p className="field-hint">{project?.role === 'owner' ? 'Owners can assign work to project owners or editors.' : 'Only the project owner can assign work to another member.'}</p>
        <label htmlFor="task-description">Task details <span className="subtle">(optional)</span></label><textarea id="task-description" value={description} onChange={e => setDescription(e.target.value)} rows={3} maxLength={8000} placeholder="Context, links, and what done looks like" disabled={busy}/>
      </>}
      <ErrorMessage message={error || memberError}/><button className="primary" type="submit" disabled={busy || loading || Boolean(memberError)}>{busy ? 'Saving…' : editing ? 'Save changes' : isProject ? 'Create project ↗' : 'Add task ↗'}</button>
    </form>
  </Modal>;
}
