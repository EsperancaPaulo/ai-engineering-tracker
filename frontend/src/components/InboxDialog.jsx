import React,{useEffect,useState} from 'react';
import {Modal,ErrorMessage} from './Shared.jsx';
export default function InboxDialog({api,onClose}){
 const [items,setItems]=useState([]),[error,setError]=useState('');
 useEffect(()=>{let active=true;api('/api/inbox').then(value=>{if(active)setItems(value);}).catch(error=>{if(active)setError(error.message);});return()=>{active=false;};},[]);
 async function read(item){try{await api(`/api/inbox/${item.id}/read`,{method:'PATCH'});setItems(values=>values.map(value=>value.id===item.id?{...value,read:true}:value));}catch(error){setError(error.message);}}
 return <Modal title="Your notifications" titleId="inbox-title" onClose={onClose}><p className="subtle">Assignments and urgent task changes in projects you still belong to.</p><ErrorMessage message={error}/>{!items.length&&<p className="field-hint">No notifications yet.</p>}{items.map(item=><article className="inbox-notice" key={item.id}><p>{item.message}</p>{item.read?<small>Read</small>:<button type="button" className="secondary" onClick={()=>read(item)}>Mark as read</button>}</article>)}</Modal>;
}
