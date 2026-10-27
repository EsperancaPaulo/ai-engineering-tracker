import React,{useState} from 'react';
import {jsonOptions} from '../api.js';
import {ErrorMessage,Modal} from './Shared.jsx';
import AutomationPreview from './AutomationPreview.jsx';

const MAX_BYTES=256*1024;
export default function FileImportDialog({project,api,onClose,onSaved}){
 const [file,setFile]=useState(null),[preview,setPreview]=useState(null),[selected,setSelected]=useState([]);
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const [custom,setCustom]=useState(false),[columns,setColumns]=useState(null),[mapping,setMapping]=useState({title:'',description:'',priority:''});
 function clearReview(){setPreview(null);setSelected([]);setError('');}
 function changeMapping(field,value){clearReview();setMapping(current=>({...current,[field]:value}));}
 async function readColumns(){
  if(!file)return;setBusy(true);clearReview();setColumns(null);
  try{const value=await api(`/api/projects/${project.id}/files/columns`,{method:'POST',headers:{'Content-Type':'text/csv; charset=utf-8'},body:file});setColumns(value.columns);setMapping(Object.fromEntries(['title','description','priority'].map(field=>[field,String(value.columns.find(column=>column.label.trim().toLowerCase()===field)?.index??'')])));}
  catch(error){setError(error.message);}finally{setBusy(false);}
 }
 function choose(event){
  const next=event.target.files?.[0]||null;setCustom(false);setColumns(null);setMapping({title:'',description:'',priority:''});setPreview(null);setSelected([]);setError('');setFile(null);
  if(!next)return;
  if(!/\.(csv|eml)$/i.test(next.name)){setError('Choose a CSV task list or an .eml email file.');return;}
  if(!next.size||next.size>MAX_BYTES){setError('Choose a nonempty file no larger than 256 KB.');return;}
  setFile(next);
 }
 async function load(event){
  event.preventDefault();if(!file)return;setBusy(true);setError('');setSelected([]);
  try{
   const headers={'Content-Type':file.name.toLowerCase().endsWith('.eml')?'message/rfc822':'text/csv; charset=utf-8'};
   if(custom){if(!columns||mapping.title==='')throw new Error('Choose a source column for the task title.');const chosen=Object.fromEntries(Object.entries(mapping).filter(([,value])=>value!=='').map(([field,value])=>[field,Number(value)]));if(new Set(Object.values(chosen)).size!==Object.keys(chosen).length)throw new Error('Choose a different source column for each field.');headers['X-CSV-Mapping']=JSON.stringify(chosen);}
   setPreview(null);setPreview(await api(`/api/projects/${project.id}/files/preview`,{method:'POST',headers,body:file}));
  }
  catch(error){setPreview(null);setError(error.message);}finally{setBusy(false);}
 }
 async function submit(){
  setBusy(true);setError('');
  try{
   const result=await api(`/api/projects/${project.id}/files/import`,jsonOptions({preview_token:preview.preview_token,row_numbers:selected}));
   await onSaved(`${result.imported_count} task${result.imported_count===1?'':'s'} imported. ${result.skipped_row_numbers.length} duplicate${result.skipped_row_numbers.length===1?'':'s'} skipped.`);onClose();
  }catch(error){setError(error.message);}finally{setBusy(false);}
 }
 const available=preview?.rows.filter(row=>!row.duplicate_reason)||[];
 const maximum=preview?.maximum_selection||25;
 return <Modal title="Import tasks from a file" titleId="file-import-title" onClose={onClose}>
  <p className="subtle">Bring a task list into {project.name} without retyping it. Review the rows before saving.</p>
  <section className="file-import-help"><a className="template-link" href="/api/task-import-template.csv" download="task-import-template.csv">Download CSV template ↗</a><p>CSV UTF-8 (up to 100 rows) or one .eml email · up to 256 KB. Use title, description and priority headings, or choose your own columns below. Title is required; blank priorities become Medium.</p><p>Files are processed locally by this app and are not sent to AI. The original file is not stored. Email attachments and remote images are ignored.</p></section>
  <form onSubmit={load}><label htmlFor="task-csv">Task list file</label><input id="task-csv" type="file" accept=".csv,.eml,text/csv,message/rfc822" onChange={choose} disabled={busy}/>{file&&!file.name.toLowerCase().endsWith('.eml')&&<section className="file-column-mapping"><label className="mapping-toggle"><input type="checkbox" checked={custom} disabled={busy} onChange={e=>{setCustom(e.target.checked);clearReview();}}/>Choose my CSV columns</label>{custom&&<><p className="field-hint">Match your headings to task fields. Other columns are ignored, including statuses and assignments. Nothing is saved here.</p><button className="secondary" type="button" disabled={busy} onClick={readColumns}>Read column headings</button>{columns&&<><div className="column-mapping-fields">{[['title','Task title'],['description','Task details'],['priority','Priority']].map(([field,label])=><div key={field}><label htmlFor={'map-'+field}>{label} column{field==='title'?' (required)':''}</label><select id={'map-'+field} value={mapping[field]} disabled={busy} onChange={e=>changeMapping(field,e.target.value)}><option value="">{field==='title'?'Choose a column':field==='priority'?'Use Medium':'Leave details empty'}</option>{columns.map(column=><option key={column.index} value={column.index}>Column {column.index+1}: {column.label}</option>)}</select></div>)}</div><p className="field-hint">Priority values must be low, medium or high. Preview and select rows before importing. Mappings apply only to this file and are not saved as a preset.</p></>}</>}</section>}<button className="secondary" type="submit" disabled={busy||!file||(custom&&(!columns||mapping.title===''))}>{busy?'Working…':'Preview file'}</button></form>
  <ErrorMessage message={error}/>
  {preview&&<>
   <div className="file-preview-summary" role="status">Ready: {available.length} · Duplicates: {preview.rows.length-available.length} · Invalid: {preview.errors.length}</div>
   {preview.errors.length>0&&<section className="file-row-errors" aria-label="Rows needing correction"><h3>Rows needing correction</h3><p>These rows cannot be imported. Correct the file and preview again, or select other valid rows.</p><ul>{preview.errors.map(row=><li key={row.row_number}>Row {row.row_number}: {row.message}</li>)}</ul></section>}
   <p className="field-hint">Select up to {maximum} rows. New tasks start as To do. Enabled rules can set priority, assign a member, or add checklist text; otherwise tasks are assigned to you. Nothing is saved until you confirm.</p>
   <button type="button" className="secondary" disabled={busy||!available.length} onClick={()=>setSelected(available.slice(0,maximum).map(row=>row.row_number))}>Select first {Math.min(available.length,maximum)} ready rows</button>
   {selected.length>0&&<button type="button" className="secondary" disabled={busy} onClick={()=>setSelected([])}>Clear selection</button>}
   <div className="file-preview-rows">{preview.rows.map(row=><article className="file-preview-row" key={row.row_number}>
    <label><input type="checkbox" checked={selected.includes(row.row_number)} disabled={busy||Boolean(row.duplicate_reason)||(!selected.includes(row.row_number)&&selected.length>=maximum)} onChange={e=>setSelected(values=>e.target.checked?[...values,row.row_number]:values.filter(number=>number!==row.row_number))}/><span>Row {row.row_number}: {row.title}</span></label>
    <p className={`priority ${row.automation?.priority||row.priority}`}>{row.automation?.priority||row.priority}</p>
    {row.duplicate_reason&&<p className="field-hint">{row.duplicate_reason}</p>}
    <details><summary>Task details</summary><p>{row.description||'No description provided.'}</p></details><AutomationPreview effect={row.automation} priority={row.priority}/>
   </article>)}</div>
   <p className="field-hint">Identical title, description and priority are skipped. Changed rows create new tasks; existing tasks are never overwritten.</p>
   <button className="primary" type="button" disabled={busy||!selected.length} onClick={submit}>Import {selected.length} selected task{selected.length===1?'':'s'}</button>
  </>}
 </Modal>;
}
