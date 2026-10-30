import React,{useCallback,useEffect,useRef,useState} from 'react';
import {jsonOptions} from '../api.js';
import {EmptyState,ErrorMessage} from './Shared.jsx';
const date=value=>new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'short'}).format(new Date(value));
const labels={assignment:'Assignment',reminder:'Reminder',progress:'Project progress'};
export default function UpdatesPage({api,onChanged,onOpenTask,onOpenProject,refreshKey=0}){
 const [page,setPage]=useState(null),[reminders,setReminders]=useState([]),[unread,setUnread]=useState(false),[category,setCategory]=useState('all');
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const request=useRef(0),mounted=useRef(true);
 const load=useCallback(async(cursor=null)=>{
  const id=++request.current;setBusy(true);setError('');
  try{
   const result=await api(`/api/updates?unread=${unread}&category=${category}${cursor?'&cursor='+cursor:''}`);
   const pending=await api('/api/reminders');
   if(mounted.current&&id===request.current){setPage(result);setReminders(pending);onChanged();}
  }catch(e){if(mounted.current&&id===request.current)setError(e.message);}
  finally{if(mounted.current&&id===request.current)setBusy(false);}
 },[api,unread,category,onChanged]);
 useEffect(()=>{mounted.current=true;setPage(null);load();return()=>{mounted.current=false;request.current++;};},[load,refreshKey]);
 useEffect(()=>{const timer=setInterval(()=>{if(!document.hidden)load();},60000);return()=>clearInterval(timer);},[load]);
 async function act(action){setBusy(true);setError('');try{await action();if(mounted.current)await load();}catch(e){if(mounted.current){setError(e.message);setBusy(false);}}}
 return <section className="updates-page" aria-label="Your updates">
  <div className="updates-intro"><div><span className="eyebrow">EVERYTHING IN ONE PLACE</span><h2>Your updates</h2><p>Assignments, personal reminders and project progress. Visible only while you still belong to the project.</p></div><span className="unread-total">{page?.unread_count??0} unread</span></div>
  <p className="updates-delivery">Checked about once a minute while the tracker is open and signed in. Due reminders catch up when you return. No email, Slack or desktop push is sent.</p>
  <ErrorMessage message={error}/>
  <div className="updates-toolbar"><label className="updates-check"><input type="checkbox" checked={unread} disabled={busy} onChange={e=>setUnread(e.target.checked)}/>Unread only</label><div><label htmlFor="update-category">Update type</label><select id="update-category" value={category} disabled={busy} onChange={e=>setCategory(e.target.value)}><option value="all">All updates</option><option value="assignment">Assignments</option><option value="reminder">Reminders</option><option value="progress">Project progress</option></select></div><button type="button" className="secondary" disabled={busy} onClick={()=>load()}>Refresh updates</button><button type="button" className="secondary" disabled={busy||!page?.unread_count} onClick={()=>act(()=>api('/api/updates/read-all',{method:'POST'}))}>Mark all as read</button></div>
  {busy&&<p className="field-hint" role="status">Checking your updates…</p>}
  {page&&!page.items.length&&<EmptyState title={unread?'You’re all caught up.':'A quiet moment.'}>{unread?'There are no unread updates in this view.':'New assignments, due reminders and observed progress changes will appear here.'}</EmptyState>}
  <div className="updates-list">{page?.items.map(item=><article key={item.id} className={`update-card ${item.read?'is-read':'is-unread'}`}><div className="update-card-meta"><span className="update-type">{labels[item.category]}</span><span>{item.read?'Read':'Unread'}</span><time dateTime={item.created_at}>{date(item.created_at)}</time></div><h3>{item.message}</h3><p className="subtle">{item.project_name}</p><div className="update-actions">{item.task_id&&<button type="button" className="secondary" disabled={busy} onClick={()=>onOpenTask(item.task_id)}>Open task</button>}<button type="button" className="secondary" disabled={busy} onClick={()=>onOpenProject(item.project_id)}>View project progress</button><button type="button" className="text-button" disabled={busy} onClick={()=>act(()=>api(`/api/updates/${item.id}`,jsonOptions({read:!item.read},'PATCH')))}>{item.read?'Mark as unread':'Mark as read'}</button></div></article>)}</div>
  {page?.next_cursor&&<button type="button" className="secondary" disabled={busy} onClick={()=>load(page.next_cursor)}>Older updates</button>}
  <section className="upcoming-reminders"><div className="section-heading"><div><span className="eyebrow">ON YOUR SCHEDULE</span><h2>Upcoming reminders</h2></div></div><p className="subtle">Use Remind me on an open task to set a personal reminder. This does not change the task’s deadline, status or assignee.</p>{!reminders.length&&<p className="field-hint">No active reminders.</p>}{reminders.map(item=><article className="upcoming-reminder" key={item.task_id}><div><strong>{item.title}</strong><p>{item.project_name} · {date(item.remind_at)}</p></div><button type="button" className="secondary" disabled={busy} onClick={()=>onOpenTask(item.task_id)}>Open task</button><button type="button" className="text-button" disabled={busy} onClick={()=>act(()=>api(`/api/reminders/${item.task_id}`,{method:'DELETE'}))}>Cancel reminder</button></article>)}</section>
  {page&&<label className="updates-check progress-preference"><input type="checkbox" checked={page.progress_enabled} disabled={busy} onChange={e=>{const enabled=e.target.checked;act(()=>api('/api/update-preferences',jsonOptions({enabled},'PATCH')));}}/>Show project progress changes</label>}
  <p className="field-hint">Progress notices compare real completed and total task counts since your previous check. Repeated identical checkpoints are kept once. Assignment notices can be adjusted in Account.</p>
 </section>;
}
