import React,{useEffect,useState} from 'react';
import {jsonOptions} from '../api.js';
import {ErrorMessage,Modal} from './Shared.jsx';
const empty={name:'',keyword:'',match_field:'title',priority:'',assigned_to:'',checklist:''};
export default function AutomationRulesDialog({project,api,onClose,onSaved}){
 const [rules,setRules]=useState([]),[members,setMembers]=useState([]),[form,setForm]=useState(empty),[saved,setSaved]=useState(null);
 const [dirty,setDirty]=useState(true),[busy,setBusy]=useState(true),[error,setError]=useState(''),[example,setExample]=useState({title:'',description:'',priority:'medium'}),[preview,setPreview]=useState(null);
 async function load(){
  setBusy(true);setError('');try{const [list,team]=await Promise.all([api(`/api/projects/${project.id}/rules`),api(`/api/projects/${project.id}/members`)]);setRules(list);setMembers(team.filter(member=>member.role!=='viewer'));}catch(error){setError(error.message);}finally{setBusy(false);}
 }
 useEffect(()=>{load();},[]);
 function change(field,value){setForm(values=>({...values,[field]:value}));setDirty(true);setPreview(null);}
 function edit(rule){setSaved(rule);setForm({name:rule.name,keyword:rule.keyword,match_field:rule.match_field,priority:rule.priority||'',assigned_to:rule.assigned_to||'',checklist:rule.checklist.join('\n')});setDirty(false);setPreview(null);setError('');}
 function updateList(rule){setRules(values=>values.some(value=>value.id===rule.id)?values.map(value=>value.id===rule.id?rule:value):[...values,rule]);setSaved(rule);}
 async function save(event){
  event.preventDefault();setBusy(true);setError('');
  const body={...form,priority:form.priority||null,assigned_to:form.assigned_to?Number(form.assigned_to):null,checklist:form.checklist.split('\n').map(line=>line.trim()).filter(Boolean)};
  if(saved)body.revision=saved.revision;
  try{const rule=await api(`/api/projects/${project.id}/rules${saved?'/'+saved.id:''}`,jsonOptions(body,saved?'PUT':'POST'));updateList(rule);setDirty(false);setPreview(null);await onSaved('Rule saved as draft. Preview an example before enabling it.');}catch(error){setError(error.message);}finally{setBusy(false);}
 }
 async function test(){
  setBusy(true);setError('');setPreview(null);
  try{setPreview(await api(`/api/projects/${project.id}/rules/${saved.id}/preview`,jsonOptions({samples:[example]})));}catch(error){setError(error.message);}finally{setBusy(false);}
 }
 async function state(rule,enabled){
  setBusy(true);setError('');
  try{const updated=await api(`/api/projects/${project.id}/rules/${rule.id}/state`,jsonOptions({enabled,revision:rule.revision,...(enabled?{preview_token:preview.preview_token}:{})},'PATCH'));setRules(values=>values.map(value=>value.id===updated.id?updated:value));if(saved?.id===updated.id){setSaved(updated);setPreview(null);}await onSaved(enabled?'Rule enabled for future imports.':'Rule paused. Existing tasks are unchanged.');}catch(error){setError(error.message);}finally{setBusy(false);}
 }
 const result=preview?.results[0];
 return <Modal title="Import automation rules" titleId="rules-title" onClose={onClose}>
  <p className="subtle">For {project.name}. Rules organize new CSV and GitHub imports without AI charges. They do not change existing tasks or send notifications.</p>
  <p className="field-hint">Case-insensitive keyword matching. First matching enabled rule wins, in creation order. Up to 20 reusable rules.</p>
  <ErrorMessage message={error}/>
  <div className="automation-rule-list">{rules.map((rule,index)=><article key={rule.id}><div><strong>{index+1}. {rule.name}</strong><span>{rule.enabled?'Enabled':'Draft / paused'}</span><p>“{rule.keyword}” in {rule.match_field==='both'?'title or description':rule.match_field}</p></div><button type="button" className="secondary" disabled={busy} onClick={()=>edit(rule)}>Edit {rule.name}</button>{rule.enabled&&<button type="button" className="secondary" disabled={busy} onClick={()=>state(rule,false)}>Pause {rule.name}</button>}</article>)}</div>
  <button type="button" className="secondary" disabled={busy||rules.length>=20} onClick={()=>{setSaved(null);setForm(empty);setDirty(true);setPreview(null);setError('');}}>New rule</button>
  <h3 className="rule-form-heading">{saved?'Edit rule':'Create a draft rule'}</h3>
  <form onSubmit={save}>
   <label htmlFor="rule-name">Rule name</label><input id="rule-name" value={form.name} maxLength={80} required disabled={busy} onChange={e=>change('name',e.target.value)}/>
   <label htmlFor="rule-keyword">Contains keyword</label><input id="rule-keyword" value={form.keyword} maxLength={80} required disabled={busy} onChange={e=>change('keyword',e.target.value)}/>
   <label htmlFor="rule-field">Look in</label><select id="rule-field" value={form.match_field} disabled={busy} onChange={e=>change('match_field',e.target.value)}><option value="title">Title</option><option value="description">Description</option><option value="both">Title or description</option></select>
   <label htmlFor="rule-priority">Priority action</label><select id="rule-priority" value={form.priority} disabled={busy} onChange={e=>change('priority',e.target.value)}><option value="">Keep imported priority</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select>
   <label htmlFor="rule-assignee">Assign matching imports to</label><select id="rule-assignee" value={form.assigned_to} disabled={busy} onChange={e=>change('assigned_to',e.target.value)}><option value="">Person importing</option>{members.map(member=><option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select>
   <label htmlFor="rule-checklist">Checklist to add (one item per line)</label><textarea id="rule-checklist" rows={3} value={form.checklist} maxLength={1300} disabled={busy} onChange={e=>change('checklist',e.target.value)}/><p className="field-hint">Up to 10 items, 120 characters each. Checklist text is added once when the task is imported.</p>
   <button className="secondary" type="submit" disabled={busy||(!dirty&&Boolean(saved))}>{saved?'Save changes as draft':'Save draft'}</button>
  </form>
  {saved&&<section className="automation-test" aria-label="Rule example preview">
   <h3>Preview before enabling</h3><p className="field-hint">Use an example that contains your keyword. This tests this rule alone; earlier enabled rules can take precedence during import. No tasks are saved.</p>
   <label htmlFor="rule-example-title">Example task title</label><input id="rule-example-title" value={example.title} maxLength={200} disabled={busy} onChange={e=>{setExample(value=>({...value,title:e.target.value}));setPreview(null);}}/>
   <label htmlFor="rule-example-details">Example task details</label><textarea id="rule-example-details" value={example.description} maxLength={8000} rows={2} disabled={busy} onChange={e=>{setExample(value=>({...value,description:e.target.value}));setPreview(null);}}/>
   <button className="secondary" type="button" disabled={busy||dirty||!example.title.trim()} onClick={test}>Preview this rule</button>
   {dirty&&<p className="field-hint">Save your changes before previewing.</p>}
   {result&&<div className="automation-result" role="status"><strong>{result.matched?'This example matches.':'This example does not match.'}</strong><p>Priority: {result.before.priority} → {result.after.priority}</p><p>Assigned to: {result.after.assignee_name||'Person importing'}</p><pre>{result.after.description||'No task details.'}</pre></div>}
   <button className="primary" type="button" disabled={busy||dirty||saved.enabled||!preview?.preview_token} onClick={()=>state(saved,true)}>Enable rule for future imports</button>
  </section>}
 </Modal>;
}
