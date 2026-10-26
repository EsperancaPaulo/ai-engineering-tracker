import React from 'react';
import {act,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {it,expect,vi} from 'vitest';
import App from '../App.jsx';
import Auth from '../components/Auth.jsx';
import Workspace from '../components/Workspace.jsx';
import ItemDialog from '../components/ItemDialog.jsx';
import TeamDialog from '../components/TeamDialog.jsx';
import DeleteDialog from '../components/DeleteDialog.jsx';
vi.mock('../components/HumanVerification.jsx',()=>({default:function Human({onToken}){React.useEffect(()=>onToken('fixture-human-token'),[onToken]);return <div>Verification fixture</div>;}}));
const user={id:1,name:'Test Owner'};
const project={id:1,name:'Engineering project',description:'A useful project',role:'owner'};
const task={id:1,title:'Original task',description:'Acceptance criteria',project_id:1,assigned_to:1,assignee_name:'Test Owner',priority:'medium',status:'done',can_edit:true};
const members=[{user_id:1,name:'Test Owner',role:'owner'},{user_id:2,name:'Demo Editor',role:'editor'}];
function workspaceApi(role='owner') {return vi.fn(async path=>{
 if(path==='/api/projects')return [{...project,role}];
 if(path==='/api/tasks'||path==='/api/tasks?scope=team')return [{...task,can_edit:role!=='viewer'}];
 if(path==='/api/activity')return [];
 if(path.endsWith('/members'))return members;
 return {};
});}
function appFetch(expires=1800){return vi.fn(async path=>{
 if(path==='/auth/config')return Response.json({human_verification:{ready:true,mode:'required',site_key:'fixture-public-key'}});
 if(path==='/auth/login')return Response.json({access_token:'temporary-test-token',expires_in:expires});
 if(path==='/me')return Response.json(user);
 return Response.json(await workspaceApi()(path));
});}
async function credentials(actor){await actor.type(screen.getByLabelText('Email address'),'test@example.com');await actor.type(screen.getByLabelText('Password'),'test-only-long-passphrase');await actor.click(within(document.querySelector('#auth-form')).getByRole('button',{name:'Sign in',exact:true}));}
it('registers without a client role and uses the OAuth email form',async()=>{
 const actor=userEvent.setup(),signedIn=vi.fn(),fetch=appFetch();vi.stubGlobal('fetch',fetch);render(<Auth onSignIn={signedIn}/>);
 await actor.click(screen.getByRole('button',{name:'Create account',exact:true}));await actor.type(screen.getByLabelText('Your name'),'Test Owner');
 await actor.type(screen.getByLabelText('Email address'),'test@example.com');await actor.type(screen.getByLabelText('Password'),'test-only-long-passphrase');await actor.type(screen.getByLabelText('Confirm password'),'test-only-long-passphrase');await waitFor(()=>expect(within(document.querySelector('#auth-form')).getByRole('button',{name:'Create account',exact:true}).disabled).toBe(false));await actor.click(within(document.querySelector('#auth-form')).getByRole('button',{name:'Create account',exact:true}));
 await waitFor(()=>expect(signedIn).toHaveBeenCalledOnce());
 expect(JSON.parse(fetch.mock.calls.find(([p])=>p==='/auth/register')[1].body)).toEqual({name:'Test Owner',email:'test@example.com',password:'test-only-long-passphrase',human_token:'fixture-human-token'});
 expect(fetch.mock.calls.find(([p])=>p==='/auth/login')[1].body.get('username')).toBe('test@example.com');
});
it('keeps a failed login on the sign-in screen',async()=>{
 const actor=userEvent.setup(),signedIn=vi.fn();vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({detail:'Invalid credentials'},{status:401})));
 render(<Auth onSignIn={signedIn}/>);await credentials(actor);expect((await screen.findByRole('alert')).textContent).toBe('Invalid credentials');expect(signedIn).not.toHaveBeenCalled();
});
it('clears workspace data on sign out without storing tokens in the browser',async()=>{
 const actor=userEvent.setup();vi.stubGlobal('fetch',appFetch());render(<App/>);await credentials(actor);await screen.findByRole('heading',{name:'Engineering project'});
 expect(localStorage.length).toBe(0);expect(sessionStorage.length).toBe(0);await actor.click(screen.getByRole('button',{name:'Sign out'}));
 expect(screen.queryByText('Original task')).toBe(null);expect(screen.queryByText('Engineering project')).toBe(null);expect(screen.getByRole('heading',{name:'Welcome back.'})).toBeTruthy();
});
it('ends expired sessions',async()=>{
 vi.useFakeTimers();vi.stubGlobal('fetch',appFetch(1));render(<App/>);
 fireEvent.change(screen.getByLabelText('Email address'),{target:{value:'test@example.com'}});fireEvent.change(screen.getByLabelText('Password'),{target:{value:'test-only-long-passphrase'}});
 await act(async()=>{fireEvent.submit(document.querySelector('#auth-form'));});expect(screen.getByRole('button',{name:'Sign out'})).toBeTruthy();
 await act(async()=>{await vi.advanceTimersByTimeAsync(1001);});expect(screen.getByRole('alert').textContent).toContain('Your session has ended');expect(screen.queryByText('Engineering project')).toBe(null);
});
it('does not expose editing to project viewers',async()=>{
 render(<Workspace user={user} api={workspaceApi('viewer')} onSignOut={vi.fn()} notify={vi.fn()}/>);await screen.findByRole('heading',{name:'Engineering project'});
 expect(screen.queryByRole('button',{name:'Edit project Engineering project'})).toBe(null);expect(screen.queryByRole('button',{name:'Delete project Engineering project'})).toBe(null);expect(screen.queryByRole('button',{name:'Edit task Original task'})).toBe(null);
 expect(screen.getByLabelText('Status for Original task').disabled).toBe(true);expect(screen.getByText('Acceptance criteria')).toBeTruthy();
});
it('preserves animation controls, team view and task search',async()=>{
 const actor=userEvent.setup();render(<Workspace user={user} api={workspaceApi()} onSignOut={vi.fn()} notify={vi.fn()}/>);await screen.findByRole('heading',{name:'Engineering project'});
 await actor.click(screen.getByRole('button',{name:'Pause animation'}));expect(document.querySelector('.welcome-banner').classList.contains('motion-paused')).toBe(true);
 await actor.click(screen.getByRole('button',{name:'Resume animation'}));expect(document.querySelector('.welcome-banner').classList.contains('motion-paused')).toBe(false);
 await actor.selectOptions(screen.getByLabelText('Task view'),'team');expect(screen.getByRole('heading',{name:'Team tasks'})).toBeTruthy();
 await actor.type(screen.getByPlaceholderText('Find a task…'),'no matching title');expect(screen.queryByText('Original task')).toBe(null);expect(screen.getByText('No matching tasks.')).toBeTruthy();
});
it('ignores workspace responses after unmount',async()=>{
 let resolve;const delayed=new Promise(value=>{resolve=value;});const api=vi.fn(path=>path==='/api/projects'?delayed:Promise.resolve([]));
 const {unmount}=render(<Workspace user={user} api={api} onSignOut={vi.fn()} notify={vi.fn()}/>);unmount();await act(async()=>{resolve([project]);await delayed;});expect(screen.queryByText('Engineering project')).toBe(null);
});
it('edits task details without overwriting status',async()=>{
 const actor=userEvent.setup(),api=vi.fn(async path=>path.endsWith('/members')?members:{}),close=vi.fn();
 render(<ItemDialog mode="task" item={task} projects={[project]} user={user} api={api} onClose={close} onSaved={vi.fn()}/>);await waitFor(()=>expect(screen.getByRole('button',{name:'Save changes'}).disabled).toBe(false));
 await actor.clear(screen.getByLabelText('Task title'));await actor.type(screen.getByLabelText('Task title'),'Revised task');await actor.selectOptions(screen.getByLabelText('Priority'),'high');await actor.click(screen.getByRole('button',{name:'Save changes'}));
 const call=api.mock.calls.find(([path])=>path==='/api/tasks/1'),body=JSON.parse(call[1].body);expect(call[1].method).toBe('PATCH');expect(body.title).toBe('Revised task');expect(body.priority).toBe('high');expect(body.description).toBe('Acceptance criteria');expect(body.status).toBeUndefined();expect(close).toHaveBeenCalledOnce();
});
it('keeps failed saves open without losing task input',async()=>{
 const actor=userEvent.setup(),api=vi.fn(async path=>{if(path.endsWith('/members'))return members;throw new Error('Project access changed');}),close=vi.fn();
 render(<ItemDialog mode="task" item={task} projects={[project]} user={user} api={api} onClose={close} onSaved={vi.fn()}/>);await waitFor(()=>expect(screen.getByRole('button',{name:'Save changes'}).disabled).toBe(false));await actor.click(screen.getByRole('button',{name:'Save changes'}));
 expect((await screen.findByRole('alert')).textContent).toBe('Project access changed');expect(screen.getByLabelText('Task title').value).toBe('Original task');expect(close).not.toHaveBeenCalled();
});
it('shows a read-only team screen for viewers',async()=>{
 render(<TeamDialog project={{...project,role:'viewer'}} user={user} api={vi.fn().mockResolvedValue(members)} onClose={vi.fn()} onSaved={vi.fn()}/>);await screen.findByText('Demo Editor');
 expect(screen.queryByLabelText('Project role')).toBe(null);expect(screen.queryByRole('button',{name:'Remove Demo Editor from project'})).toBe(null);
});
it('cancels deletion safely without making a request',async()=>{
 const actor=userEvent.setup(),api=vi.fn(),close=vi.fn();render(<DeleteDialog mode="task" item={task} api={api} onClose={close} onSaved={vi.fn()}/>);
 expect(document.activeElement).toBe(screen.getByRole('button',{name:'Keep it'}));await actor.click(screen.getByRole('button',{name:'Keep it'}));expect(api).not.toHaveBeenCalled();expect(close).toHaveBeenCalledOnce();
});
it('keeps protected project deletion open with an explanation',async()=>{
 const actor=userEvent.setup(),close=vi.fn();render(<DeleteDialog mode="project" item={project} api={vi.fn().mockRejectedValue(new Error('This project still has tasks.'))} onClose={close} onSaved={vi.fn()}/>);await actor.click(screen.getByRole('button',{name:'Delete permanently'}));expect((await screen.findByRole('alert')).textContent).toBe('This project still has tasks.');expect(close).not.toHaveBeenCalled();
});

it('rolls back a failed task status change and shows the reason',async()=>{
 const actor=userEvent.setup(),base=workspaceApi(),api=vi.fn((path,options)=>options?.method==='PATCH'?Promise.reject(new Error('Cannot update task')):base(path));
 render(<Workspace user={user} api={api} onSignOut={vi.fn()} notify={vi.fn()}/>);await screen.findByRole('heading',{name:'Engineering project'});
 await actor.selectOptions(screen.getByLabelText('Status for Original task'),'in_progress');
 expect((await screen.findByRole('alert')).textContent).toBe('Cannot update task');
 expect(screen.getByLabelText('Status for Original task').value).toBe('done');
 expect(JSON.parse(api.mock.calls.find(([,options])=>options?.method==='PATCH')[1].body)).toEqual({status:'in_progress'});
});
it('shows live password requirements and refuses submission until every check passes',async()=>{
 const actor=userEvent.setup(),fetch=appFetch(),signedIn=vi.fn();vi.stubGlobal('fetch',fetch);render(<Auth onSignIn={signedIn}/>);
 await actor.click(screen.getByRole('button',{name:'Create account',exact:true}));
 expect(screen.queryByText(/Use a long, original passphrase/)).toBe(null);
 await actor.type(screen.getByLabelText('Your name'),'Test Owner');await actor.type(screen.getByLabelText('Email address'),'test@example.com');
 const password=screen.getByLabelText('Password'),confirm=screen.getByLabelText('Confirm password'),submit=within(document.querySelector('#auth-form')).getByRole('button',{name:'Create account',exact:true});
 fireEvent.change(password,{target:{value:'Password123456789!'}});fireEvent.change(confirm,{target:{value:'Password123456789!'}});
 expect(screen.getByRole('list',{name:'Password requirements'}).textContent).toContain('Not a common password or known example: not passed');expect(submit.disabled).toBe(true);
 fireEvent.submit(document.querySelector('#auth-form'));expect(fetch.mock.calls.some(([path])=>path==='/auth/register')).toBe(false);
 fireEvent.change(password,{target:{value:'cobalt lanterns drift beyond seven orchards'}});fireEvent.change(confirm,{target:{value:'different'}});
 await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('Strong'));expect(submit.disabled).toBe(true);
 fireEvent.change(confirm,{target:{value:'cobalt lanterns drift beyond seven orchards'}});
 await waitFor(()=>expect(submit.disabled).toBe(false));
 expect([...document.querySelectorAll('#password-checks li')].every(item=>item.dataset.passed==='true')).toBe(true);
 fireEvent.change(password,{target:{value:'short'}});expect(submit.disabled).toBe(true);
});
