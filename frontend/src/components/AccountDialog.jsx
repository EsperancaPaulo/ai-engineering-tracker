import React,{useEffect,useState} from 'react';
import {jsonOptions} from '../api.js';
import {Modal,ErrorMessage} from './Shared.jsx';
export default function AccountDialog({user,api,onClose}){
 const [state,setState]=useState(null),[error,setError]=useState(''),[message,setMessage]=useState('');
 useEffect(()=>{let active=true;api('/auth/account').then(value=>{if(active)setState(value);}).catch(error=>{if(active)setError(error.message);});return()=>{active=false;};},[]);
 async function preference(enabled){setError('');try{await api('/auth/notifications',jsonOptions({enabled},'PATCH'));setState(value=>({...value,notifications_enabled:enabled}));}catch(error){setError(error.message);}}
 async function verify(){setError('');try{const value=await api('/auth/email-action',jsonOptions({email:user.email,kind:'verify'}));setMessage(value.message);}catch(error){setError(error.message);}}
 return <Modal title="Your account" titleId="account-title" onClose={onClose}><p>{user.name}</p><p className="field-hint">{user.email}</p><ErrorMessage message={error}/>{state&&<><label><input style={{width:'auto',marginRight:8}} type="checkbox" checked={state.notifications_enabled!==false} onChange={e=>preference(e.target.checked)}/>In-app assignment notifications</label><p className="automation-result">Email: {state.email_verified?'verified':'not verified yet'}</p>{!state.email_verified&&<button type="button" className="secondary" disabled={!state.email_service_ready||Boolean(message)} onClick={verify}>Email me a verification link</button>}{!state.email_service_ready&&<p className="field-hint">Account email delivery is waiting for private mail-server setup. Existing sign-in works.</p>}</>}{message&&<p role="status" className="field-hint">{message}</p>}</Modal>;
}
