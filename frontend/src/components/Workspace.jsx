import React, {useCallback, useEffect, useRef, useState} from 'react';
import {jsonOptions} from '../api.js';
import {Action, activitySummary, Brand, EmptyState, ErrorMessage, roleLabels, SectionHeading, statusLabels} from './Shared.jsx';
import GitHubImportDialog from './GitHubImportDialog.jsx';
import FileImportDialog from './FileImportDialog.jsx';
import AutomationRulesDialog from './AutomationRulesDialog.jsx';
import ItemDialog from './ItemDialog.jsx';
import TeamDialog from './TeamDialog.jsx';
import DeleteDialog from './DeleteDialog.jsx';
import ProjectReportDialog from './ProjectReportDialog.jsx';
import UpdatesPage from './UpdatesPage.jsx';
import TaskReminderDialog from './TaskReminderDialog.jsx';
import AccountDialog from './AccountDialog.jsx';
import GmailDialog from './GmailDialog.jsx';

const emptyData = {projects: [], tasks: [], teamTasks: [], activity: []};
const titles = {
  updates: ['Stay in the loop.', 'Your work, reminders and progress. Together.'],
  overview: ['Your next chapter.', 'A little more focused. A little further forward.'],
  projects: ['Ideas into action.', 'Your projects. Your team. Your momentum.'],
  tasks: ['Make your next move.', 'One focused task at a time.'],
  activity: ['Look how far you’ve come.', 'A record of the work that moves you forward.'],
};
export default function Workspace({user, api, onSignOut, notify}) {
  const [data, setData] = useState(emptyData), [view, setView] = useState('overview');
  const [error, setError] = useState(''), [loading, setLoading] = useState(true), [dialog, setDialog] = useState(null);
  const [scope, setScope] = useState('mine'), [search, setSearch] = useState(''), [filter, setFilter] = useState('all');
  const [paused, setPaused] = useState(false);
  const generation = useRef(0), mounted = useRef(true);
  const [unreadCount,setUnreadCount]=useState(0),[updatesError,setUpdatesError]=useState(''),[updatesVersion,setUpdatesVersion]=useState(0);
  const updateCheck=useRef(false);
  const refreshUpdates=useCallback(async()=>{
    if(updateCheck.current)return;updateCheck.current=true;
    try{const result=await api('/api/updates/summary');if(mounted.current){setUnreadCount(Number(result.unread_count)||0);setUpdatesError('');}}catch(e){if(mounted.current)setUpdatesError('Updates could not be checked. Open Updates to retry.');}finally{updateCheck.current=false;}
  },[api]);
  useEffect(()=>{refreshUpdates();const check=()=>{if(!document.hidden)refreshUpdates();};const timer=setInterval(check,60000);window.addEventListener('focus',check);return()=>{clearInterval(timer);window.removeEventListener('focus',check);};},[refreshUpdates]);
  const reminderSaved=useCallback(()=>{setUpdatesVersion(value=>value+1);refreshUpdates();},[refreshUpdates]);
  async function openTask(taskId){try{const task=await api(`/api/updates/tasks/${taskId}`);if(mounted.current)setDialog({type:'reminder',task});}catch(e){if(mounted.current)notify(e.message);}}
  function openProgress(projectId){const project=data.projects.find(value=>value.id===projectId);if(project)setDialog({type:'report',project});else notify('This project is no longer available. Refresh your workspace.');}
  const refresh = useCallback(async () => {
    const request = ++generation.current;
    setError(''); setLoading(true);
    try {
      const [projects, tasks, activity, teamTasks] = await Promise.all([api('/api/projects'), api('/api/tasks'), api('/api/activity'), api('/api/tasks?scope=team')]);
      if (mounted.current && request === generation.current) setData({projects,tasks,activity,teamTasks});
    } catch(error) {if (mounted.current && request === generation.current) setError(error.message);}
    finally {if (mounted.current && request === generation.current) setLoading(false);}
  }, [api]);
  useEffect(() => {mounted.current = true; refresh(); return () => {mounted.current = false; generation.current++;};}, [refresh]);
  const {projects, tasks, activity, teamTasks} = data;
  async function saved(message) {await refresh();refreshUpdates(); if (mounted.current) notify(message);}
  function create(mode, projectId) {
    if (mode === 'task' && !projects.length) {notify('Create a project first, then add your tasks.'); setDialog({type:'item',mode:'project'}); return;}
    if (mode === 'task' && !projects.some(p => p.role !== 'viewer')) {notify('You need owner or editor access to add tasks.'); return;}
    setDialog({type:'item',mode,projectId});
  }
  const done = tasks.filter(task => task.status === 'done').length;
  const source = scope === 'team' ? teamTasks : tasks;
  const visibleTasks = source.filter(task => task.title.toLowerCase().includes(search.toLowerCase()) && (filter === 'all' || task.status === filter));
  const sectionVisible = section => view === 'overview' || view === section;
  const date = new Intl.DateTimeFormat(undefined,{weekday:'long',month:'long',day:'numeric'}).format(new Date()).toUpperCase();
  return <div className="app-shell" id="app-view">
    <aside className="sidebar"><Brand sidebar/><p className="nav-label">WORKSPACE</p><nav aria-label="Main navigation">{[['overview','◫','Overview'],['projects','▤','Projects'],['tasks','✓','My tasks'],['activity','◷','Activity'],['updates','◉','Updates']].map(([key,icon,label]) => <button key={key} type="button" className={`nav-item ${view === key ? 'active' : ''}`} aria-current={view === key ? 'page' : undefined} onClick={() => setView(key)}><span aria-hidden="true">{icon}</span>{label}</button>)}</nav>
      <div className="sidebar-bottom"><button type="button" className="profile profile-account" aria-label="Open account settings" onClick={()=>setDialog({type:'account'})}><span className="avatar">{user.name.slice(0,1).toUpperCase()}</span><span><strong>{user.name}</strong><small>Account settings</small></span></button><button type="button" className="logout" onClick={onSignOut}>Sign out</button></div>
    </aside>
    <div className="workspace"><header className="topbar"><span>Workspace / {view === 'tasks' ? 'My tasks' : view[0].toUpperCase() + view.slice(1)}</span><span className="connection"><span className="signal"/>{loading ? 'Updating your workspace…' : error ? 'Workspace needs attention' : 'Connected to your workspace'}</span><div className="topbar-actions"><button type="button" className="secondary" onClick={()=>setDialog({type:'account'})}>Account</button><button type="button" className="notification-bell" aria-label={`Notifications, ${unreadCount} unread`} title={updatesError||'Open your updates'} onClick={()=>{setView('updates');refreshUpdates();}}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>{unreadCount>0&&<span className="notification-count">{unreadCount>99?'99+':unreadCount}</span>}</button></div></header>
      <main className="main-content"><div className="page-heading"><div><p className="eyebrow">{date}</p><h1>{titles[view][0]}</h1><p>{titles[view][1]}</p></div><button type="button" className="primary compact" onClick={() => create('project')}>+ New project</button></div>
        <ErrorMessage message={error}/>{error && <button type="button" className="secondary" onClick={refresh} disabled={loading}>Retry connection</button>}
        {loading && <p className="loading-note" role="status">Updating your workspace…</p>}
        {updatesError&&<p className="field-hint" role="status">{updatesError}</p>}
        {view==='updates'&&<UpdatesPage api={api} refreshKey={updatesVersion} onChanged={refreshUpdates} onOpenTask={openTask} onOpenProject={openProgress}/>}
        {view === 'overview' && <section id="overview-section"><div className={`welcome-banner ${paused ? 'motion-paused' : ''}`}><div><span className="eyebrow">BUILD WITH INTENTION</span><h2>Good to see you, {user.name.split(' ')[0]}.</h2><p>Choose one task. Move one idea forward.<br/>Your future self will thank you.</p><button type="button" className="text-button" onClick={() => setView('tasks')}>Find your next task <span aria-hidden="true">↗</span></button></div><Orbit/><button type="button" className="motion-control" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? 'Resume animation' : 'Pause animation'}</button></div>
          <div className="stats">{[['Your projects',projects.length,'Ideas with a place to grow'],['Tasks in progress',tasks.filter(t => t.status === 'in_progress').length,'Your current focus'],['Tasks completed',done,'Every finish is a win'],['Completion rate',`${tasks.length ? Math.round(done/tasks.length*100) : 0}%`,'Across your personal tasks']].map(([label,value,hint]) => <article key={label}><span>{label}</span><strong>{value}</strong><small>{hint}</small></article>)}</div>
        </section>}
        {sectionVisible('projects') && <section className="content-section" id="projects-section"><SectionHeading eyebrow="IDEAS INTO ACTION" title="Your projects"><span className="subtle">Only visible to project members</span></SectionHeading><div className="project-grid">
          {!projects.length && !loading && <EmptyState title="A blank canvas. A good place to start.">Create your first project, then break it into small, achievable tasks.</EmptyState>}
          {projects.map(project => {
            const personal = tasks.filter(t => t.project_id === project.id), completed = personal.filter(t => t.status === 'done').length;
            const rate = personal.length ? Math.round(completed/personal.length*100) : 0;
            return <article className="project-card" key={project.id}><div className="project-card-top"><span className="project-icon" aria-hidden="true">⌘</span><span className="tag">{roleLabels[project.role]}</span></div><h3>{project.name}</h3><p>{project.description || 'Your next great idea starts here.'}</p><div className="project-progress"><div className="project-count"><span>{completed} / {personal.length} of your tasks done</span><span>{rate}%</span></div><div className="progress-track"><div className="progress-fill" style={{width:`${rate}%`}}/></div>{project.role !== 'viewer' && <button type="button" className="text-button" onClick={() => create('task',project.id)}>Add a task ↗</button>}<div className="item-actions">
              {project.role !== 'viewer' && <Action label={`Edit project ${project.name}`} onClick={() => setDialog({type:'item',mode:'project',item:project})}>Edit</Action>}
              {project.role === 'owner' && <Action label={`Delete project ${project.name}`} onClick={() => setDialog({type:'delete',mode:'project',item:project})}>Delete</Action>}
              {project.role === 'owner' && <Action label={`Import GitHub issues into ${project.name}`} onClick={() => setDialog({type:'github',project})}>Import issues</Action>}
              {project.role === 'owner' && <Action label={`Import file tasks into ${project.name}`} onClick={() => setDialog({type:'file',project})}>Import file</Action>}
              {project.role === 'owner' && <Action label={`Review Gmail drafts for ${project.name}`} onClick={() => setDialog({type:'gmail',project})}>Gmail drafts</Action>}
              {project.role === 'owner' && <Action label={`Manage automation rules for ${project.name}`} onClick={() => setDialog({type:'rules',project})}>Rules</Action>}
              <Action label={`View report for ${project.name}`} onClick={()=>setDialog({type:'report',project})}>Report & updates</Action>
              <Action label={`View team for ${project.name}`} onClick={() => setDialog({type:'team',project})}>Team</Action>
            </div></div></article>;
          })}
        </div></section>}
        {sectionVisible('tasks') && <section className="content-section" id="tasks-section"><SectionHeading eyebrow="ONE STEP AT A TIME" title={scope === 'team' ? 'Team tasks' : 'My tasks'}><button type="button" className="secondary" onClick={() => create('task')}>+ Add task</button></SectionHeading>
          <div className="task-toolbar"><label className="sr-only" htmlFor="task-scope">Task view</label><select id="task-scope" value={scope} onChange={e => setScope(e.target.value)}><option value="mine">My tasks</option><option value="team">Team tasks</option></select><label className="search-box" htmlFor="task-search"><span aria-hidden="true">⌕</span><input id="task-search" type="search" placeholder="Find a task…" value={search} onChange={e => setSearch(e.target.value)}/></label><label className="sr-only" htmlFor="status-filter">Filter by status</label><select id="status-filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All statuses</option>{Object.entries(statusLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></div>
          <div className="tasks-list">{!visibleTasks.length && !loading && <EmptyState title={source.length ? 'No matching tasks.' : 'Make space for your first small win.'}>{source.length ? 'Try another search or status.' : 'Add a task to a project and take the next step.'}</EmptyState>}{visibleTasks.map(task => <TaskRow key={task.id} task={task} project={projects.find(p => p.id === task.project_id)} api={api} onSaved={saved} onError={setError} onEdit={() => setDialog({type:'item',mode:'task',item:task})} onDelete={() => setDialog({type:'delete',mode:'task',item:task})} onRemind={()=>openTask(task.id)}/>)}</div>
        </section>}
        {sectionVisible('activity') && <section className="content-section" id="activity-section"><SectionHeading eyebrow="THE WORK ADDS UP" title="Recent activity"><span className="subtle">Your latest 20 updates</span></SectionHeading><div className="activity-list">{!activity.length && !loading && <EmptyState title="Your story starts here.">Create a project or task to record your first milestone.</EmptyState>}{activity.map(item => <article className="activity-row" key={item.id}><span className="activity-dot" aria-hidden="true">↗</span><div><strong>{item.action}</strong><p>{activitySummary(item.details)}</p></div><time dateTime={item.created_at}>{new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(item.created_at))}</time></article>)}</div></section>}
        <footer className="workspace-footer">AI Engineering Tracker <span>Build something you’re proud of.</span></footer>
      </main>
    </div>
    {dialog?.type === 'item' && <ItemDialog key={`${dialog.mode}-${dialog.item?.id || 'new'}`} {...dialog} initialProjectId={dialog.projectId} projects={projects} user={user} api={api} onClose={() => setDialog(null)} onSaved={saved}/>}
    {dialog?.type === 'github' && <GitHubImportDialog project={dialog.project} api={api} onClose={() => setDialog(null)} onSaved={saved}/>}
    {dialog?.type === 'file' && <FileImportDialog project={dialog.project} api={api} onClose={() => setDialog(null)} onSaved={saved}/>}
    {dialog?.type === 'gmail' && <GmailDialog project={dialog.project} api={api} onClose={()=>setDialog(null)} onSaved={saved}/>}
    {dialog?.type === 'rules' && <AutomationRulesDialog project={dialog.project} api={api} onClose={() => setDialog(null)} onSaved={saved}/>}
    {dialog?.type === 'report' && <ProjectReportDialog project={dialog.project} api={api} onClose={()=>setDialog(null)} onSaved={saved}/>}
    {dialog?.type === 'reminder' && <TaskReminderDialog task={dialog.task} api={api} onClose={()=>setDialog(null)} onSaved={reminderSaved}/>}
    {dialog?.type === 'account' && <AccountDialog user={user} api={api} onClose={()=>setDialog(null)}/>}
    {dialog?.type === 'team' && <TeamDialog project={dialog.project} user={user} api={api} onClose={() => setDialog(null)} onSaved={saved}/>}
    {dialog?.type === 'delete' && <DeleteDialog {...dialog} api={api} onClose={() => setDialog(null)} onSaved={saved}/>}
  </div>;
}
function TaskRow({task,project,api,onSaved,onError,onEdit,onDelete,onRemind}) {
  const [busy,setBusy] = useState(false), [pendingStatus,setPendingStatus] = useState(null);
  async function changeStatus(value) {
    setBusy(true); setPendingStatus(value);
    try {await api(`/api/tasks/${task.id}`, jsonOptions({status:value},'PATCH')); await onSaved('Task updated. Keep moving forward.');}
    catch(error) {onError(error.message);} finally {setBusy(false); setPendingStatus(null);}
  }
  return <article className="task-row"><div className="task-title">{task.title}<small>{project?.name || 'Project'} · {task.assignee_name || 'Unassigned'}</small>{task.description && <p className="task-description">{task.description}</p>}</div><span className={`priority ${task.priority}`}>{task.priority}</span><div className="task-controls"><select aria-label={`Status for ${task.title}`} value={pendingStatus ?? task.status} disabled={busy || !task.can_edit} onChange={e => changeStatus(e.target.value)}>{Object.entries(statusLabels).map(([value,label]) => <option value={value} key={value}>{label}</option>)}</select>{task.status!=='done'&&<button type="button" className="remind-task" aria-label={`Set reminder for ${task.title}`} onClick={onRemind}>Remind me</button>}{task.can_edit && <div className="item-actions"><Action label={`Edit task ${task.title}`} onClick={onEdit} disabled={busy}>Edit</Action><Action label={`Delete task ${task.title}`} onClick={onDelete} disabled={busy}>Delete</Action></div>}</div></article>;
}
function Orbit() {
  return <div className="orbit-art" aria-hidden="true"><span className="orbit one"/><span className="orbit two"/><span className="orbit three"/><span className="orbit-core"><svg className="network-symbol" viewBox="0 0 48 48" fill="none" focusable="false"><path d="M12 13 24 24 36 12M24 24 35 36M24 24 11 35M12 13 36 12M11 35 35 36" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>{[[24,24,5],[12,13,3.5],[36,12,3.5],[11,35,3.5],[35,36,3.5]].map(([cx,cy,r]) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} fill="currentColor"/>)}</svg></span><span className="orbit-dot"/></div>;
}
