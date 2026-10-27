import React from 'react';
import {render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {it,expect,vi} from 'vitest';
import GitHubImportDialog from '../components/GitHubImportDialog.jsx';
const project={id:1,name:'Project',role:'owner'};
it('previews without saving, renders untrusted text safely, and imports only selected issues',async()=>{
 const actor=userEvent.setup(),saved=vi.fn(),close=vi.fn();
 const api=vi.fn(async path=>path.endsWith('/preview')?{page:1,has_next:false,preview_token:'fixture-preview',issues:[{id:1,number:3,title:'<img src=x onerror=alert(1)>',body:'Untrusted issue text',url:'https://github.com/demo/repo/issues/3',already_imported:false},{id:2,number:4,title:'Duplicate issue',body:'',url:'https://github.com/demo/repo/issues/4',already_imported:true}]}:{imported_count:1,skipped_issue_numbers:[]});
 render(<GitHubImportDialog project={project} api={api} onClose={close} onSaved={saved}/>);
 await actor.type(screen.getByLabelText('Repository'),'demo/repo');await actor.click(screen.getByRole('button',{name:'Preview issues'}));
 const check=await screen.findByRole('checkbox',{name:'#3 <img src=x onerror=alert(1)>'});
 expect(document.querySelector('img')).toBe(null);expect(screen.getByRole('checkbox',{name:/Duplicate issue/}).disabled).toBe(true);
 expect(api).toHaveBeenCalledOnce();await actor.click(check);await actor.click(screen.getByRole('button',{name:'Import 1 selected issue'}));
 await waitFor(()=>expect(close).toHaveBeenCalledOnce());
 const body=JSON.parse(api.mock.calls[1][1].body);expect(body).toEqual({preview_token:'fixture-preview',issue_numbers:[3]});expect(saved).toHaveBeenCalledOnce();
});
it('does not import automatically when the repository has no open issues',async()=>{
 const actor=userEvent.setup(),api=vi.fn().mockResolvedValue({page:1,has_next:false,preview_token:'fixture-preview',issues:[]});render(<GitHubImportDialog project={project} api={api} onClose={vi.fn()} onSaved={vi.fn()}/>);
 await actor.type(screen.getByLabelText('Repository'),'demo/repo');await actor.click(screen.getByRole('button',{name:'Preview issues'}));await screen.findByText('No open issues on this page. Pull requests are excluded.');
 expect(api).toHaveBeenCalledOnce();expect(screen.getByRole('button',{name:'Import 0 selected issues'}).disabled).toBe(true);
});
it('generates only on request and requires separate approval before applying AI drafts',async()=>{
 const actor=userEvent.setup(),close=vi.fn();
 const issue={id:1,number:3,title:'Broken export',body:'Export fails for large files.',url:'https://github.com/demo/repo/issues/3',already_imported:false};
 const suggestion={summary:'Large exports fail.','priority':'high','rationale':'Reported export failure.','source_quote':'Export fails','model':'fixture'};
 const api=vi.fn(async path=>path.endsWith('/preview')?{page:1,has_next:false,preview_token:'original',ai:{ready:true},issues:[issue]}:path.endsWith('/analyze')?{preview_token:'reviewed',issues:[{...issue,ai_suggestion:suggestion}]}:{imported_count:1,skipped_issue_numbers:[]});
 render(<GitHubImportDialog project={project} api={api} onClose={close} onSaved={vi.fn()}/>);
 await actor.type(screen.getByLabelText('Repository'),'demo/repo');await actor.click(screen.getByRole('button',{name:'Preview issues'}));
 const selected=await screen.findByRole('checkbox',{name:'#3 Broken export'});expect(api).toHaveBeenCalledOnce();
 await actor.click(selected);await actor.click(screen.getByRole('button',{name:'Send to OpenAI & draft suggestions'}));
 const approval=await screen.findByRole('checkbox',{name:'Approve AI summary and high priority for #3'});
 expect(approval.checked).toBe(false);expect(close).not.toHaveBeenCalled();expect(api).toHaveBeenCalledTimes(2);
 expect(JSON.parse(api.mock.calls[1][1].body)).toEqual({preview_token:'original',issue_numbers:[3],consent:true});
 await actor.click(approval);await actor.click(selected);expect(approval.checked).toBe(false);expect(approval.disabled).toBe(true);
 await actor.click(selected);await actor.click(approval);await actor.click(screen.getByRole('button',{name:'Import 1 selected issue'}));
 await waitFor(()=>expect(close).toHaveBeenCalledOnce());
 expect(JSON.parse(api.mock.calls[2][1].body)).toEqual({preview_token:'reviewed',issue_numbers:[3],accepted_ai_numbers:[3]});
});
it('keeps original import available after AI generation fails',async()=>{
 const actor=userEvent.setup();
 const api=vi.fn(async path=>{if(path.endsWith('/analyze'))throw new Error('AI is unavailable');return {page:1,has_next:false,preview_token:'original',ai:{ready:true},issues:[{id:1,number:3,title:'Issue',body:'Details',url:'https://github.com/demo/repo/issues/3'}]};});
 render(<GitHubImportDialog project={project} api={api} onClose={vi.fn()} onSaved={vi.fn()}/>);
 await actor.type(screen.getByLabelText('Repository'),'demo/repo');await actor.click(screen.getByRole('button',{name:'Preview issues'}));
 await actor.click(await screen.findByRole('checkbox',{name:'#3 Issue'}));await actor.click(screen.getByRole('button',{name:'Send to OpenAI & draft suggestions'}));
 expect((await screen.findByRole('alert')).textContent).toBe('AI is unavailable');expect(screen.getByRole('button',{name:'Import 1 selected issue'}).disabled).toBe(false);
});
