import React from 'react';
import {render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {it,expect,vi} from 'vitest';
import ProjectReportDialog from '../components/ProjectReportDialog.jsx';
import InboxDialog from '../components/InboxDialog.jsx';
it('shows measured reports and never sends Slack updates on opening or preview',async()=>{
 const actor=userEvent.setup();
 const api=vi.fn(async path=>path.endsWith('/report')?{total_tasks:3,statuses:{done:1},high_priority_open:1,imported_tasks_history:2,automated_tasks_history:1,completion_percent:33}:path.endsWith('/integrations')?{slack:{ready:true,destination:'Test channel',sending_enabled:false}}:{text:'Reviewed update',destination:'Test channel',preview_token:'fixture',sending_enabled:false,already_attempted:false});
 render(<ProjectReportDialog project={{id:1,name:'Project',role:'owner'}} api={api} onClose={vi.fn()} onSaved={vi.fn()}/>);
 await actor.click(await screen.findByRole('button',{name:'Preview Slack message'}));
 expect(await screen.findByText('Reviewed update')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Confirm & send reviewed message'}).disabled).toBe(true);
 expect(api.mock.calls.some(([path])=>path.endsWith('/send'))).toBe(false);
});
it('marks only the selected inbox notice as read',async()=>{
 const actor=userEvent.setup(),api=vi.fn(async path=>path==='/api/inbox'?[{id:4,message:'Task assigned',read:false}]:null);
 render(<InboxDialog api={api} onClose={vi.fn()}/>);await actor.click(await screen.findByRole('button',{name:'Mark as read'}));
 await screen.findByText('Read');expect(api.mock.calls[1][0]).toBe('/api/inbox/4/read');
});
