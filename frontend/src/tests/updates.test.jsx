import React from 'react';
import {render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {expect,it,vi} from 'vitest';
import UpdatesPage from '../components/UpdatesPage.jsx';
import TaskReminderDialog from '../components/TaskReminderDialog.jsx';
import Workspace from '../components/Workspace.jsx';
const item={id:8,message:'Reminder: Check release',category:'reminder',read:false,created_at:'2026-10-30T10:00:00Z',project_id:1,project_name:'Release project',task_id:4};
const props=()=>({onChanged:vi.fn(),onOpenTask:vi.fn(),onOpenProject:vi.fn()});
it('shows unread updates, opens task/project and persists read/unread actions',async()=>{
 const actor=userEvent.setup(),callbacks=props();let read=false;
 const api=vi.fn(async(path,options)=>{
  if(path==='/api/reminders')return [];
  if(path==='/api/updates/8'){read=JSON.parse(options.body).read;return {read};}
  return {items:[{...item,read}],unread_count:read?0:1,progress_enabled:true,next_cursor:null};
 });
 render(<UpdatesPage api={api} {...callbacks}/>);
 await actor.click(await screen.findByRole('button',{name:'Open task'}));expect(callbacks.onOpenTask).toHaveBeenCalledWith(4);
 await actor.click(screen.getByRole('button',{name:'View project progress'}));expect(callbacks.onOpenProject).toHaveBeenCalledWith(1);
 await actor.click(screen.getByRole('button',{name:'Mark as read',exact:true}));await screen.findByRole('button',{name:'Mark as unread'});
 expect(JSON.parse(api.mock.calls.find(([path])=>path==='/api/updates/8')[1].body)).toEqual({read:true});
 await actor.click(screen.getByRole('button',{name:'Mark as unread'}));await screen.findByRole('button',{name:'Mark as read',exact:true});
 expect(callbacks.onChanged).toHaveBeenCalled();
});
it('filters and pages the feed, cancels personal reminders and changes progress preferences',async()=>{
 const actor=userEvent.setup();let reminders=[{task_id:4,title:'Check release',project_name:'Release project',remind_at:'2026-10-31T10:00:00Z'}];
 const api=vi.fn(async(path,options)=>{
  if(path==='/api/reminders')return reminders;
  if(path==='/api/reminders/4'){reminders=[];return null;}
  return {items:[],unread_count:0,progress_enabled:true,next_cursor:path.includes('cursor=')?null:10};
 });
 render(<UpdatesPage api={api} {...props()}/>);await screen.findByRole('button',{name:'Cancel reminder'});
 await actor.selectOptions(screen.getByLabelText('Update type'),'progress');await waitFor(()=>expect(api.mock.calls.some(([path])=>path.includes('category=progress'))).toBe(true));
 await actor.click(screen.getByRole('checkbox',{name:'Unread only'}));await waitFor(()=>expect(api.mock.calls.some(([path])=>path.includes('unread=true'))).toBe(true));
 await actor.click(screen.getByRole('button',{name:'Older updates'}));await waitFor(()=>expect(api.mock.calls.some(([path])=>path.includes('cursor=10'))).toBe(true));
 await actor.click(screen.getByRole('button',{name:'Cancel reminder'}));await waitFor(()=>expect(screen.queryByRole('button',{name:'Cancel reminder'})).toBe(null));
 await actor.click(screen.getByRole('checkbox',{name:'Show project progress changes'}));await waitFor(()=>expect(api.mock.calls.some(([path])=>path==='/api/update-preferences')).toBe(true));
 expect(api.mock.calls.some(([path])=>/slack|email/.test(path))).toBe(false);
});
it('keeps a failed read action visible and reports a useful retry error',async()=>{
 const actor=userEvent.setup(),api=vi.fn(async path=>{if(path==='/api/updates/8')throw new Error('Save failed. Please retry.');return path==='/api/reminders'?[]:{items:[item],unread_count:1,progress_enabled:true};});
 render(<UpdatesPage api={api} {...props()}/>);await actor.click(await screen.findByRole('button',{name:'Mark as read',exact:true}));
 expect((await screen.findByRole('alert')).textContent).toContain('Save failed');expect(screen.getByRole('button',{name:'Mark as read',exact:true})).toBeTruthy();
});
it('saves a deliberate reminder without changing task fields or sending externally',async()=>{
 const actor=userEvent.setup(),saved=vi.fn(),api=vi.fn().mockResolvedValue({task_id:4,remind_at:'2026-10-30T11:00:00Z'});
 render(<TaskReminderDialog task={{id:4,title:'Check release',status:'todo',priority:'high',assignee_name:'Owner',description:'Review criteria'}} api={api} onClose={vi.fn()} onSaved={saved}/>);
 await actor.selectOptions(screen.getByLabelText('Remind me in'),'1');await actor.click(screen.getByRole('button',{name:'Save personal reminder'}));
 await screen.findByRole('status');expect(api.mock.calls[0][0]).toBe('/api/reminders/4');expect(JSON.parse(api.mock.calls[0][1].body)).toEqual({minutes:1});expect(saved).toHaveBeenCalledOnce();
});
it('does not offer reminders for completed tasks',()=>{
 render(<TaskReminderDialog task={{id:4,title:'Finished',status:'done',priority:'low'}} api={vi.fn()} onClose={vi.fn()} onSaved={vi.fn()}/>);
 expect(screen.queryByRole('button',{name:'Save personal reminder'})).toBe(null);expect(screen.getByText(/Completed tasks do not send reminders/)).toBeTruthy();
});
it('uses the bell to open Updates without leaving the tracker',async()=>{
 const actor=userEvent.setup(),api=vi.fn(async path=>{
  if(path==='/api/updates/summary')return {unread_count:2};
  if(path.startsWith('/api/updates?'))return {items:[item],unread_count:2,progress_enabled:true};
  return [];
 });
 render(<Workspace user={{id:1,name:'Owner'}} api={api} notify={vi.fn()} onSignOut={vi.fn()}/>);
 await actor.click(await screen.findByRole('button',{name:'Notifications, 2 unread'}));
 expect(await screen.findByRole('heading',{name:'Your updates'})).toBeTruthy();expect(screen.getByRole('heading',{name:'Stay in the loop.'})).toBeTruthy();
 expect(screen.getByText('Reminder: Check release')).toBeTruthy();
});
it('replaces the decorative sidebar prompt with a real account action',async()=>{
 const actor=userEvent.setup(),api=vi.fn(async path=>path==='/auth/account'?{email_verified:true,notifications_enabled:true,email_service_ready:true}:path==='/api/updates/summary'?{unread_count:0}:[]);
 render(<Workspace user={{id:1,name:'Owner',email:'owner@example.com'}} api={api} notify={vi.fn()} onSignOut={vi.fn()}/>);
 expect(screen.queryByText(/Big things start/)).toBe(null);
 await actor.click(screen.getByRole('button',{name:'Open account settings'}));expect(await screen.findByRole('heading',{name:'Your account'})).toBeTruthy();
});
it('refreshes Upcoming reminders immediately after saving from an update task link',async()=>{
 const actor=userEvent.setup();let scheduled=false;
 const api=vi.fn(async(path,options)=>{
  if(path==='/api/updates/summary')return {unread_count:1};
  if(path.startsWith('/api/updates?'))return {items:[item],unread_count:1,progress_enabled:true};
  if(path==='/api/updates/tasks/4')return {id:4,title:'Check release',description:'Check criteria',priority:'high',status:'todo'};
  if(path==='/api/reminders/4'){scheduled=true;return {task_id:4,remind_at:'2026-10-31T10:00:00Z'};}
  if(path==='/api/reminders')return scheduled?[{task_id:4,title:'Check release',project_name:'Release project',remind_at:'2026-10-31T10:00:00Z'}]:[];
  return [];
 });
 render(<Workspace user={{id:1,name:'Owner'}} api={api} notify={vi.fn()} onSignOut={vi.fn()}/>);
 await actor.click(await screen.findByRole('button',{name:'Notifications, 1 unread'}));await actor.click(await screen.findByRole('button',{name:'Open task',exact:true}));
 await actor.click(await screen.findByRole('button',{name:'Save personal reminder'}));await screen.findByRole('status');await actor.click(screen.getByRole('button',{name:'Close dialog'}));
 expect(await screen.findByRole('button',{name:'Cancel reminder'})).toBeTruthy();
});
