'use strict';
const $ = id => document.getElementById(id);
let token = null, user = null, projects = [], tasks = [], activity = [];
let authMode = 'login', currentView = 'overview', createMode = 'project', editingId = null, pendingDelete = null, expiryTimer, toastTimer;
const statusLabels = {todo: 'To do', in_progress: 'In progress', done: 'Done'};
function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
function errorAt(id, message) { $(id).textContent = message; $(id).hidden = !message; }
function notify(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4000); }
function signOut(message = '') { clearTimeout(expiryTimer); token = null; user = null; projects = []; tasks = []; activity = []; $('create-dialog').close(); $('delete-dialog').close(); pendingDelete = null; $('app-view').hidden = true; $('auth-view').hidden = false; $('auth-form').reset(); setAuthMode('login'); errorAt('auth-error', message); $('email').focus(); }
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {...(token ? {Authorization: `Bearer ${token}`} : {}), ...options.headers}, cache: 'no-store'});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && token) { signOut('Your session has ended. Please sign in again.'); throw new Error('Please sign in again.'); }
    let message = typeof data.detail === 'string' ? data.detail : 'Please check your entries and try again.';
    if (Array.isArray(data.detail)) message = data.detail.map(e => `${e.loc.at(-1)}: ${e.msg}`).join('. ');
    if (response.status >= 500) message = 'Your workspace could not be reached. Please try again.';
    throw new Error(message);
  }
  return data;
}
function jsonOptions(data, method = 'POST') { return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)}; }
function setAuthMode(mode) {
  authMode = mode; const registering = mode === 'register';
  $('auth-heading').textContent = registering ? 'Start your next chapter.' : 'Welcome back.';
  $('auth-subtitle').textContent = registering ? 'Create a workspace for your progress.' : 'Sign in and pick up where you left off.';
  $('name-field').hidden = !registering; $('name').required = registering;
  $('password-hint').hidden = !registering; $('password').minLength = registering ? 15 : 1;
  $('password').autocomplete = registering ? 'new-password' : 'current-password';
  $('auth-submit').textContent = registering ? 'Create account ↗' : 'Sign in ↗';
  $('login-tab').classList.toggle('selected', !registering); $('register-tab').classList.toggle('selected', registering);
  $('login-tab').setAttribute('aria-pressed', String(!registering)); $('register-tab').setAttribute('aria-pressed', String(registering));
  errorAt('auth-error', '');
}
$('login-tab').onclick = () => setAuthMode('login'); $('register-tab').onclick = () => setAuthMode('register');
$('auth-form').onsubmit = async event => {
  event.preventDefault(); errorAt('auth-error', ''); $('auth-submit').disabled = true;
  try {
    const email = $('email').value.trim(), password = $('password').value;
    if (authMode === 'register') await api('/auth/register', jsonOptions({name: $('name').value.trim(), email, password}));
    const data = await api('/auth/login', {method:'POST', body: new URLSearchParams({username: email, password})});
    token = data.access_token;
    expiryTimer = setTimeout(() => signOut('Your session has ended. Please sign in again.'), data.expires_in * 1000);
    user = await api('/me');
    $('auth-form').reset();
    $('profile-name').textContent = user.name; $('avatar').textContent = user.name.slice(0,1).toUpperCase();
    $('greeting').textContent = `Good to see you, ${user.name.split(' ')[0]}.`;
    $('auth-view').hidden = true; $('app-view').hidden = false;
    setView('overview');
    await refresh();
  } catch (error) { if (!$('auth-view').hidden) errorAt('auth-error', error.message || 'Unable to connect. Check that the server is running.'); else errorAt('app-error', error.message); }
  finally { $('auth-submit').disabled = false; }
};
$('logout').onclick = () => { signOut(); notify('Signed out on this browser.'); };
$('today').textContent = new Intl.DateTimeFormat(undefined, {weekday:'long', month:'long',day:'numeric'}).format(new Date()).toUpperCase();
function setView(view) {
  currentView = view;
  document.querySelectorAll('.nav-item').forEach(button => {button.classList.toggle('active', button.dataset.view === view); if(button.dataset.view === view) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');});
  const titles = {overview:['Your next chapter.', 'A little more focused. A little further forward.'], projects:['Ideas into action.', 'Shared projects. Personal momentum.'], tasks:['Make your next move.', 'One focused task at a time.'], activity:['Look how far you’ve come.', 'A record of the work that moves you forward.']};
  $('page-title').textContent = titles[view][0]; $('page-description').textContent = titles[view][1];
  $('breadcrumb').textContent = `Workspace / ${view === 'tasks' ? 'My tasks' : view[0].toUpperCase()+view.slice(1)}`;
  for (const section of ['overview','projects','tasks','activity']) $(`${section}-section`).hidden = view !== 'overview' && view !== section;
}
document.querySelectorAll('[data-view]').forEach(button => button.onclick = () => setView(button.dataset.view));
$('focus-tasks').onclick = () => setView('tasks');
async function refresh() {
  errorAt('app-error', '');
  try { [projects, tasks, activity] = await Promise.all([api('/api/projects'),api('/api/tasks'),api('/api/activity')]); render(); }
  catch (error) { if (token) errorAt('app-error', error.message || 'Unable to connect. Please try again.'); }
}
function empty(container, heading, description) { const node = el('div','empty-state'); node.append(el('strong','',heading), el('p','',description)); container.append(node); }
function render() {
  $('stat-projects').textContent = projects.length;
  const done = tasks.filter(t => t.status === 'done').length;
  $('stat-done').textContent = done; $('stat-progress').textContent = tasks.filter(t => t.status === 'in_progress').length;
  $('stat-rate').textContent = `${tasks.length ? Math.round(done/tasks.length*100) : 0}%`;
  const list = $('projects-list'); list.replaceChildren();
  if (!projects.length) empty(list, 'A blank canvas. A good place to start.', 'Create your first project, then break it into small, achievable tasks.');
  projects.forEach(project => {
    const card = el('article','project-card'), top = el('div','project-card-top');
    top.append(el('span','project-icon','⌘'),el('span','tag','Shared project'));
    card.append(top,el('h3','',project.name),el('p','',project.description || 'Your next great idea starts here.'));
    const personal = tasks.filter(t => t.project_id === project.id), complete = personal.filter(t => t.status === 'done').length;
    const progress = el('div','project-progress'), count = el('div','project-count');
    count.append(el('span','',`${complete} / ${personal.length} of your tasks done`),el('span','',`${personal.length ? Math.round(complete/personal.length*100) : 0}%`));
    const track = el('div','progress-track'), fill = el('div','progress-fill'); fill.style.width = `${personal.length ? complete/personal.length*100 : 0}%`; track.append(fill);
    const button = el('button','text-button','Add a task ↗'); button.type = 'button'; button.onclick = () => openCreate('task', project.id);
    const actions = el('div', 'item-actions');
    const edit = actionButton('Edit', `Edit project ${project.name}`, () => openEdit('project', project));
    const remove = actionButton('Delete', `Delete project ${project.name}`, () => openDelete('project', project));
    actions.append(edit, remove);
    progress.append(count,track,button,actions); card.append(progress); list.append(card);
  });
  renderTasks();
  const activityList = $('activity-list'); activityList.replaceChildren();
  if (!activity.length) empty(activityList,'Your story starts here.', 'Create a project or task to record your first milestone.');
  activity.forEach(item => {
    const row = el('article','activity-row'), copy = el('div'); copy.append(el('strong','',item.action),el('p','',activitySummary(item.details)));
    const time = el('time','',new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(item.created_at))); time.dateTime = item.created_at;
    row.append(el('span','activity-dot','↗'),copy,time); activityList.append(row);
  });
}
function renderTasks() {
  const list = $('tasks-list'); list.replaceChildren();
  const query = $('task-search').value.toLowerCase(), filter = $('status-filter').value;
  const visible = tasks.filter(t => t.title.toLowerCase().includes(query) && (filter === 'all' || t.status === filter));
  if (!visible.length) empty(list,tasks.length ? 'No matching tasks.' : 'Make space for your first small win.',tasks.length ? 'Try another search or status.' : 'Add a task to a project and take the next step.');
  visible.forEach(task => {
    const row = el('article','task-row'), title = el('div','task-title',task.title);
    title.append(el('small','',projects.find(p => p.id === task.project_id)?.name || 'Project'));
    const select = el('select'); select.setAttribute('aria-label',`Status for ${task.title}`);
    Object.entries(statusLabels).forEach(([value,label]) => { const option = el('option','',label); option.value = value; select.append(option); }); select.value = task.status;
    select.onchange = async () => {
      select.disabled = true;
      try { await api(`/api/tasks/${task.id}`,jsonOptions({status:select.value},'PATCH')); await refresh(); notify('Task updated. Keep moving forward.'); }
      catch(error) {select.value = task.status; errorAt('app-error',error.message);}
      finally {select.disabled = false;}
    };
    const controls = el('div','task-controls'), actions = el('div','item-actions');
    actions.append(actionButton('Edit', `Edit task ${task.title}`, () => openEdit('task',task)), actionButton('Delete', `Delete task ${task.title}`, () => openDelete('task',task)));
    controls.append(select,actions);
    row.append(title,el('span',`priority ${task.priority}`,task.priority),controls); list.append(row);
  });
}
$('task-search').oninput = renderTasks; $('status-filter').onchange = renderTasks;
function openCreate(mode, projectId) {
  if (mode === 'task' && !projects.length) { notify('Create a project first, then add your tasks.'); openCreate('project'); return; }
  editingId = null; createMode = mode; const isProject = mode === 'project';
  $('create-form').reset(); errorAt('dialog-error','');
  $('dialog-title').textContent = isProject ? 'Give your idea a home.' : 'One small step forward.';
  $('dialog-hint').textContent = isProject ? 'Projects are shared with everyone in this workspace.' : 'This task will be assigned to you.';
  $('item-name-label').textContent = isProject ? 'Project name' : 'Task title'; $('item-name').maxLength = isProject ? 150 : 200;
  $('project-fields').hidden = !isProject; $('task-fields').hidden = isProject; $('task-project').required = !isProject;
  $('create-submit').textContent = isProject ? 'Create project ↗' : 'Add task ↗';
  $('task-project').replaceChildren(); projects.forEach(project => {const option = el('option','',project.name); option.value = project.id; $('task-project').append(option);});
  if (projectId) $('task-project').value = projectId;
  $('create-dialog').showModal(); $('item-name').focus();
}
$('new-project').onclick = () => openCreate('project'); $('new-task').onclick = () => openCreate('task'); $('close-dialog').onclick = () => $('create-dialog').close();
$('create-form').onsubmit = async event => {
  event.preventDefault(); $('create-submit').disabled = true; errorAt('dialog-error','');
  try {
    const isProject = createMode === 'project';
    const path = (isProject ? '/api/projects' : '/api/tasks') + (editingId === null ? '' : `/${editingId}`);
    const wasEditing = editingId !== null;
    await api(path,jsonOptions(isProject ? {name:$('item-name').value.trim(),description:$('description').value.trim()} : {title:$('item-name').value.trim(),project_id:Number($('task-project').value),priority:$('task-priority').value}, wasEditing ? (isProject ? 'PUT' : 'PATCH') : 'POST'));
    $('create-dialog').close(); await refresh(); notify(wasEditing ? 'Changes saved.' : (isProject ? 'Project created. Let’s build something.' : 'Task added. You’ve got this.'));
  } catch(error) {errorAt('dialog-error',error.message || 'Unable to connect. Please try again.');}
  finally {$('create-submit').disabled = false;}
};
setAuthMode('login');

function actionButton(label, accessibleName, action) {
  const button = el('button', label === 'Delete' ? 'item-action delete-action' : 'item-action', label);
  button.type = 'button'; button.setAttribute('aria-label',accessibleName); button.onclick = action;
  return button;
}
function activitySummary(details) {
  if (!details) return '';
  try { const parsed = JSON.parse(details); return typeof parsed.summary === 'string' ? parsed.summary : details; }
  catch { return details; }
}
function openEdit(mode, item) {
  openCreate(mode, mode === 'task' ? item.project_id : undefined);
  editingId = item.id;
  $('dialog-title').textContent = mode === 'project' ? 'Edit project' : 'Edit task';
  $('dialog-hint').textContent = mode === 'project' ? 'These changes will be visible to everyone in this workspace.' : 'Update your task details. Your current status will stay the same.';
  $('item-name').value = mode === 'project' ? item.name : item.title;
  if (mode === 'project') $('description').value = item.description || '';
  else $('task-priority').value = item.priority;
  $('create-submit').textContent = 'Save changes';
}
function openDelete(mode, item) {
  pendingDelete = {mode, id:item.id};
  $('delete-title').textContent = mode === 'project' ? 'Delete shared project?' : 'Delete task?';
  $('delete-name').textContent = mode === 'project' ? item.name : item.title;
  $('delete-description').textContent = mode === 'project' ? 'This removes the project for everyone. Projects with any remaining tasks cannot be deleted. This action cannot be undone.' : 'This permanently removes your task and updates your progress. This action cannot be undone.';
  errorAt('delete-error',''); $('delete-submit').disabled = false;
  $('delete-dialog').showModal(); $('delete-cancel').focus();
}
function closeDelete() { $('delete-dialog').close(); pendingDelete = null; }
$('delete-cancel').onclick = closeDelete;
$('delete-close').onclick = closeDelete;
$('delete-dialog').addEventListener('cancel', () => pendingDelete = null);
$('delete-form').onsubmit = async event => {
  event.preventDefault(); if (!pendingDelete) return;
  $('delete-submit').disabled = true; errorAt('delete-error','');
  try {
    const {mode,id} = pendingDelete;
    await api(`/api/${mode === 'project' ? 'projects' : 'tasks'}/${id}`,{method:'DELETE'});
    closeDelete(); await refresh(); notify(mode === 'project' ? 'Project deleted.' : 'Task deleted.');
  } catch(error) {errorAt('delete-error',error.message || 'Unable to connect. Please try again.');}
  finally {$('delete-submit').disabled = false;}
};

$('toggle-motion').onclick = () => {
  const paused = document.querySelector('.welcome-banner').classList.toggle('motion-paused');
  $('toggle-motion').setAttribute('aria-pressed', String(paused));
  $('toggle-motion').textContent = paused ? 'Resume animation' : 'Pause animation';
};
