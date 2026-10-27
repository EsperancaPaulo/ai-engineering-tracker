import React from 'react';
import {render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {it,expect,vi} from 'vitest';
import AutomationRulesDialog from '../components/AutomationRulesDialog.jsx';
import AutomationPreview from '../components/AutomationPreview.jsx';
const project={id:1,name:'Operations'};
it('saves disabled drafts and requires a matching preview before enabling',async()=>{
 const actor=userEvent.setup(),saved=vi.fn();
 const rule={id:5,name:'Outage triage',keyword:'outage',match_field:'title',priority:'high',assigned_to:null,checklist:[],enabled:false,revision:1};
 const api=vi.fn(async(path,options)=>{
  if(path.endsWith('/members'))return [{user_id:1,name:'Owner',role:'owner'},{user_id:2,name:'Viewer',role:'viewer'}];
  if(path.endsWith('/preview'))return {preview_token:'activation-fixture',results:[{matched:true,before:{priority:'medium'},after:{priority:'high',description:'',assignee_name:null}}]};
  if(path.endsWith('/state'))return {...rule,enabled:true,revision:2};
  if(options?.method==='POST')return rule;
  return [];
 });
 render(<AutomationRulesDialog project={project} api={api} onClose={vi.fn()} onSaved={saved}/>);
 await waitFor(()=>expect(screen.getByLabelText('Rule name').disabled).toBe(false));
 expect(screen.queryByRole('option',{name:'Viewer'})).toBe(null);
 await actor.type(screen.getByLabelText('Rule name'),'Outage triage');await actor.type(screen.getByLabelText('Contains keyword'),'outage');await actor.selectOptions(screen.getByLabelText('Priority action'),'high');
 await actor.click(screen.getByRole('button',{name:'Save draft'}));
 const enable=await screen.findByRole('button',{name:'Enable rule for future imports'});expect(enable.disabled).toBe(true);
 await actor.type(screen.getByLabelText('Example task title'),'Production outage');await actor.click(screen.getByRole('button',{name:'Preview this rule'}));
 await waitFor(()=>expect(enable.disabled).toBe(false));expect(screen.getByText('This example matches.')).toBeTruthy();
 await actor.click(enable);await waitFor(()=>expect(screen.getByText('Enabled')).toBeTruthy());
 const body=JSON.parse(api.mock.calls.find(([path])=>path.endsWith('/state'))[1].body);
 expect(body).toEqual({enabled:true,revision:1,preview_token:'activation-fixture'});
});
it('renders rule outcomes as text and makes approved AI priority precedence visible',()=>{
 render(<AutomationPreview effect={{rule_name:'<script>Rule</script>',priority:'low',assignee_name:'Editor',checklist:['Confirm impact']}} aiOverride/>);
 expect(document.querySelector('script')).toBe(null);expect(screen.getByText(/approved AI priority/)).toBeTruthy();expect(screen.getByText('Confirm impact')).toBeTruthy();
});
