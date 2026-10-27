import React,{useEffect,useMemo,useState} from 'react';
import {createApi,jsonOptions} from '../api.js';
import {assessPassword} from '../passwordPolicy.js';
import {ErrorMessage} from './Shared.jsx';
const api=createApi();
export default function AccountRecovery({action={},onBack}){
 const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[confirmation,setConfirmation]=useState(''),[estimator,setEstimator]=useState(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState(''),[kind,setKind]=useState('reset');
 const reset=Boolean(action.reset),verify=Boolean(action.verify);
 useEffect(()=>{if(reset)import('zxcvbn').then(module=>setEstimator(()=>module.default)).catch(()=>setError('Password checks could not load. Please refresh.'));},[reset]);
 const strength=useMemo(()=>assessPassword(password,'','',estimator),[password,estimator]);
 async function submit(event){
  event.preventDefault();setBusy(true);setError('');
  try{
   const value=verify?await api('/auth/verify-email',jsonOptions({token:action.verify})):reset?await api('/auth/reset-password',jsonOptions({token:action.reset,password})):await api('/auth/email-action',jsonOptions({email,kind}));
   setMessage(value.message);setPassword('');setConfirmation('');
  }catch(error){setError(error.message);}finally{setBusy(false);}
 }
 return <section className="recovery-panel"><h2>{verify?'Verify your email':reset?'Choose a new password':'Recover your account'}</h2><p className="subtle">{verify?'Confirm the single-use link from your inbox.':reset?'A new password revokes earlier sign-in sessions.':'Request a single-use recovery or verification link for your account.'}</p><ErrorMessage message={error}/>{message?<p role="status" className="automation-result">{message}</p>:<form onSubmit={submit}>{!reset&&!verify&&<><label htmlFor="email-link-kind">Email link type</label><select id="email-link-kind" value={kind} onChange={e=>setKind(e.target.value)}><option value="reset">Password recovery</option><option value="verify">Email verification</option></select><label htmlFor="recovery-email">Account email</label><input id="recovery-email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required maxLength={255} disabled={busy}/></>}{reset&&<><label htmlFor="new-password">New password</label><input id="new-password" type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} maxLength={128} required disabled={busy}/><p className="password-rating">Strength: {strength.label}</p><label htmlFor="new-password-confirm">Confirm new password</label><input id="new-password-confirm" type="password" autoComplete="new-password" value={confirmation} onChange={e=>setConfirmation(e.target.value)} maxLength={128} required disabled={busy}/><ul className="password-checklist">{[...strength.checks,{id:'match',label:'Passwords match',passed:Boolean(password)&&password===confirmation}].map(check=><li key={check.id} data-passed={check.passed}><span aria-hidden="true">{check.passed?'✓':'○'}</span>{check.label}</li>)}</ul></>}<button className="primary" type="submit" disabled={busy||(reset&&(!strength.valid||password!==confirmation))}>{busy?'Working…':verify?'Confirm email verification':reset?'Update password':'Email account link'}</button></form>}<button className="text-button" type="button" onClick={onBack}>Back to sign in</button></section>;
}
