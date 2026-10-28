import React from 'react';
import {render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {expect,it,vi} from 'vitest';
import GmailDialog from '../components/GmailDialog.jsx';
const project={id:1,name:'Release project',role:'owner'};
const draft={id:7,title:'Review release',description:'Check criteria',state:'pending',problem:''};
it('shows honest disconnected setup without making collection requests',async()=>{
 const api=vi.fn(async path=>path.includes('/drafts?')?{items:[],next_cursor:null}:{connected:false,project_id:1,owner_id:2});
 render(<GmailDialog project={project} api={api} onClose={vi.fn()} onSaved={vi.fn()}/>);
 await screen.findByText('Connect privately on this computer');expect(screen.queryByRole('button',{name:'Collect labelled emails'})).toBe(null);expect(api).toHaveBeenCalledTimes(2);
});
it('collects only on request and separately reviews before explicit task import',async()=>{
 const actor=userEvent.setup(),saved=vi.fn();
 const api=vi.fn(async path=>path.endsWith('/import')?{imported_count:1,skipped_count:0}:path.endsWith('/preview')?{preview_token:'fixture-review',rows:[{...draft,priority:'medium',automation:null,duplicate:false}]}:path.includes('/drafts?')?{items:[draft],next_cursor:null}:{connected:true,automatic:false,last_result:'Connected',project_id:1,owner_id:2});
 render(<GmailDialog project={project} api={api} onClose={vi.fn()} onSaved={saved}/>);
 const collect=await screen.findByRole('button',{name:'Collect labelled emails'});expect(api).toHaveBeenCalledTimes(2);
 await actor.click(collect);expect(api.mock.calls.some(([path])=>path.endsWith('/collect'))).toBe(true);expect(saved).not.toHaveBeenCalled();
 await actor.click(screen.getByRole('checkbox',{name:'Review release'}));await actor.click(screen.getByRole('button',{name:'Review 1 selected draft'}));
 await screen.findByText('Confirm task outcomes');expect(api.mock.calls.some(([path])=>path.endsWith('/import'))).toBe(false);
 await actor.click(screen.getByRole('button',{name:'Confirm & import reviewed drafts'}));await waitFor(()=>expect(saved).toHaveBeenCalledOnce());
 const call=api.mock.calls.find(([path])=>path.endsWith('/import'));expect(JSON.parse(call[1].body)).toEqual({preview_token:'fixture-review',confirmed:true});
});
it('allows restoring dismissed drafts and clears the review when selection changes',async()=>{
 const actor=userEvent.setup();
 const api=vi.fn(async path=>path.endsWith('/preview')?{preview_token:'fixture',rows:[{...draft,priority:'medium',automation:null}]}:path.includes('/drafts?')?{items:[{...draft,state:path.includes('state=dismissed')?'dismissed':'pending'}],next_cursor:null}:{connected:true,automatic:false});
 render(<GmailDialog project={project} api={api} onClose={vi.fn()} onSaved={vi.fn()}/>);
 await actor.click(await screen.findByRole('checkbox',{name:'Review release'}));await actor.click(screen.getByRole('button',{name:'Review 1 selected draft'}));await screen.findByText('Confirm task outcomes');
 await actor.click(screen.getByRole('checkbox',{name:'Review release'}));expect(screen.queryByText('Confirm task outcomes')).toBe(null);
 await actor.selectOptions(screen.getByLabelText('Draft view'),'dismissed');await actor.click(await screen.findByRole('button',{name:'Restore Review release'}));
 expect(api.mock.calls.some(([path,options])=>path.endsWith('/drafts/7')&&JSON.parse(options.body).action==='restore')).toBe(true);
});
