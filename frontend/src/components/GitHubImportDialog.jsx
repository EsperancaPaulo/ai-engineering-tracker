import React,{useState} from 'react';
import {jsonOptions} from '../api.js';
import {ErrorMessage,Modal} from './Shared.jsx';
import AutomationPreview from './AutomationPreview.jsx';

export default function GitHubImportDialog({project,api,onClose,onSaved}){
 const [repository,setRepository]=useState(''),[preview,setPreview]=useState(null),[selected,setSelected]=useState([]);
 const [accepted,setAccepted]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function load(page=1){
  setBusy(true);setError('');setSelected([]);setAccepted([]);
  try{setPreview(await api(`/api/projects/${project.id}/github/preview`,jsonOptions({repository:repository.trim(),page})));}
  catch(error){setPreview(null);setError(error.message);}finally{setBusy(false);}
 }
 async function analyze(){
  setBusy(true);setError('');
  try{
   const result=await api(`/api/projects/${project.id}/github/analyze`,jsonOptions({preview_token:preview.preview_token,issue_numbers:selected,consent:true}));
   setPreview(value=>({...value,preview_token:result.preview_token,issues:result.issues.map(issue=>({...value.issues.find(old=>old.id===issue.id),...issue}))}));
   setAccepted(values=>values.filter(number=>!selected.includes(number)));
  }catch(error){setError(error.message);}finally{setBusy(false);}
 }
 async function submit(){
  setBusy(true);setError('');
  try{
   const payload={preview_token:preview.preview_token,issue_numbers:selected};
   if(accepted.length)payload.accepted_ai_numbers=accepted;
   const result=await api(`/api/projects/${project.id}/github/import`,jsonOptions(payload));
   await onSaved(`${result.imported_count} issue${result.imported_count===1?'':'s'} imported. ${result.skipped_issue_numbers.length} already imported.`);onClose();
  }catch(error){setError(error.message);}finally{setBusy(false);}
 }
 function select(number,checked){
  setSelected(values=>checked?[...values,number]:values.filter(value=>value!==number));
  if(!checked)setAccepted(values=>values.filter(value=>value!==number));
 }
 return <Modal title="Import GitHub issues" titleId="github-title" onClose={onClose}>
  <p className="subtle">Import open issues into {project.name}. GitHub is read-only; you choose what to save here.</p>
  <form onSubmit={event=>{event.preventDefault();load();}}>
   <label htmlFor="github-repository">Repository</label>
   <input id="github-repository" value={repository} onChange={e=>{setRepository(e.target.value);setPreview(null);setSelected([]);setAccepted([]);}} placeholder="owner/repository" maxLength={140} required disabled={busy}/>
   <button type="submit" className="secondary" disabled={busy}>{busy?'Working…':'Preview issues'}</button>
  </form><ErrorMessage message={error}/>
  {preview&&<>
   {preview.restricted_source&&<p className="automation-result">Restricted repository source: imported text becomes visible to this project’s members. AI is disabled for this source.</p>}
   <p className="field-hint">Page {preview.page}. Select up to 10 issues. Imported tasks start as To do. Enabled rules may set priority, assignee and checklist; otherwise they are assigned to you. Nothing is saved as a task until you confirm.</p>
   {preview.issues.length>0&&<section className="ai-import-help" aria-label="AI assistance">
    <h3>Optional AI assistance</h3>
    {preview.ai?.ready?<>
     <p>Select up to 3 issues. Generating drafts sends their public titles and descriptions to OpenAI. API charges apply. Your account and workspace data are not sent.</p>
     <button className="secondary" type="button" disabled={busy||!selected.length||selected.length>3} onClick={analyze}>Send to OpenAI & draft suggestions</button>
     <p>Review each draft against the original. Suggestions stay unused unless you approve them below.</p>
    </>:<p>AI suggestions are not configured yet. Original issue import is available.</p>}
   </section>}
   <div className="github-issues">
    {!preview.issues.length&&<p className="subtle">No open issues on this page. Pull requests are excluded.</p>}
    {preview.issues.map(issue=><article className="github-issue" key={issue.id}>
     <label><input type="checkbox" checked={selected.includes(issue.number)} disabled={busy||issue.already_imported||(!selected.includes(issue.number)&&selected.length>=10)} onChange={e=>select(issue.number,e.target.checked)}/><span>#{issue.number} {issue.title}{issue.already_imported&&<small>Already imported</small>}</span></label>
     <a href={issue.url} target="_blank" rel="noopener noreferrer">View on GitHub ↗</a>
     <details><summary>Original issue details</summary><p>{issue.body||'No description provided.'}</p></details>
     <AutomationPreview effect={issue.automation} aiOverride={accepted.includes(issue.number)}/>
     {issue.ai_suggestion&&<section className="ai-draft" aria-label={`AI draft for issue ${issue.number}`}>
      <h3>AI draft · review required</h3><p>{issue.ai_suggestion.summary}</p>
      <p><strong>Suggested priority: {issue.ai_suggestion.priority}</strong></p><p>{issue.ai_suggestion.rationale}</p>
      <blockquote>{issue.ai_suggestion.source_quote}</blockquote>
      <p className="field-hint">Quoted from the linked original issue. AI can make mistakes.</p>
      <label><input type="checkbox" checked={accepted.includes(issue.number)} disabled={busy||!selected.includes(issue.number)||issue.already_imported} onChange={e=>setAccepted(values=>e.target.checked?[...values,issue.number]:values.filter(value=>value!==issue.number))}/><span>Approve AI summary and {issue.ai_suggestion.priority} priority for #{issue.number}</span></label>
     </section>}
    </article>)}
   </div>
   <div className="import-pagination"><button className="secondary" type="button" disabled={busy||preview.page===1} onClick={()=>load(preview.page-1)}>Previous</button><button className="secondary" type="button" disabled={busy||!preview.has_next} onClick={()=>load(preview.page+1)}>Next</button></div>
   <p className="field-hint">{accepted.length} AI suggestion{accepted.length===1?'':'s'} approved. Approved AI priority overrides a rule priority; other rule actions still apply. Without approval, rules apply to the original issue with Medium as the default priority. Original text and source links are retained.</p>
   <button className="primary" type="button" disabled={busy||!selected.length} onClick={submit}>Import {selected.length} selected issue{selected.length===1?'':'s'}</button>
  </>}
 </Modal>;
}
