import React, {useEffect,useMemo,useState} from 'react';
import {createApi, jsonOptions} from '../api.js';
import HumanVerification from './HumanVerification.jsx';
import {assessPassword} from '../passwordPolicy.js';
import {Brand, ErrorMessage} from './Shared.jsx';
const api = createApi();

export default function Auth({onSignIn, notice = ''}) {
  const [mode, setMode] = useState('login');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const registering = mode === 'register';
  const [password,setPassword]=useState(''),[confirmation,setConfirmation]=useState(''),[name,setName]=useState(''),[email,setEmail]=useState('');
  const [estimator,setEstimator]=useState(null),[configuration,setConfiguration]=useState(null),[configError,setConfigError]=useState(''),[configRetry,setConfigRetry]=useState(0);
  const [humanToken,setHumanToken]=useState(''),[resetVersion,setResetVersion]=useState(0);
  useEffect(()=>{
    if(!registering)return;let active=true;
    import('zxcvbn').then(module=>{if(active)setEstimator(()=>module.default);}).catch(()=>{if(active)setConfigError('The local password check could not load. Please refresh.');});
    api('/auth/config').then(value=>{if(active){setConfiguration(value);setConfigError('');}}).catch(error=>{if(active)setConfigError(error.message);});
    return ()=>{active=false;};
  },[registering,configRetry]);
  const strength=useMemo(()=>assessPassword(password,name,email,estimator),[password,name,email,estimator]);
  const passwordChecks=[...strength.checks,{id:'confirmation',label:'Passwords match',passed:Boolean(password)&&confirmation===password}];
  const human=configuration?.human_verification;
  const ready=!registering||(strength.valid&&confirmation===password&&human?.ready&&Boolean(humanToken));
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const form = event.currentTarget;
    const values = new FormData(form), email = values.get('email').trim(), password = values.get('password');
    if(registering&&!ready){setError('Choose a stronger password, confirm it, and complete human verification.');setBusy(false);return;}
    try {
      if (registering) await api('/auth/register', jsonOptions({name: values.get('name').trim(), email, password, human_token:humanToken}));
      const data = await api('/auth/login', {method: 'POST', body: new URLSearchParams({username: email, password})});
      const user = await createApi(data.access_token)('/me');
      form.reset(); setPassword('');setConfirmation('');setHumanToken('');
      onSignIn({token: data.access_token, user, expiresAt: Date.now() + data.expires_in * 1000});
    } catch (error) {setError(error.message);if(registering){setHumanToken('');setResetVersion(value=>value+1);}} finally {setBusy(false);}
  }
  return <div className="auth-layout" id="auth-view">
    <section className="intro"><Brand/><div className="intro-copy"><span className="eyebrow">SMALL STEPS. REAL PROGRESS.</span><h1>Build skills.<br/>Ship projects.<br/><em>See your growth.</em></h1><p>A focused workspace for your journey in AI engineering. Turn ambitious ideas into your next completed task.</p><div className="intro-note"><span className="signal"/> Your next chapter starts with one small step.</div></div><footer>Made for the work that moves you forward.<span>01 / YOUR WORKSPACE</span></footer></section>
    <main className="auth-panel"><div className="auth-card"><span className="eyebrow">LET’S GET BUILDING</span><h2>{registering ? 'Start your next chapter.' : 'Welcome back.'}</h2><p>{registering ? 'Create a workspace for your progress.' : 'Sign in and pick up where you left off.'}</p>
      <div className="auth-tabs" role="group" aria-label="Choose account action">{[['login','Sign in'],['register','Create account']].map(([value,label]) => <button key={value} type="button" disabled={busy} aria-pressed={mode === value} className={mode === value ? 'selected' : ''} onClick={() => {setMode(value); setError('');setPassword('');setConfirmation('');setHumanToken('');}}>{label}</button>)}</div>
      <form id="auth-form" onSubmit={submit}>
        {registering && <><label htmlFor="name">Your name</label><input id="name" name="name" value={name} onChange={e=>setName(e.target.value)} autoComplete="name" maxLength={100} required disabled={busy}/></>}
        <label htmlFor="email">Email address</label><input id="email" name="email" type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="username" placeholder="you@example.com" maxLength={255} required disabled={busy}/>
        <label htmlFor="password">Password</label><input aria-describedby={registering?'password-checks':undefined} id="password" name="password" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete={registering ? 'new-password' : 'current-password'} minLength={registering ? 15 : 1} maxLength={128} required disabled={busy}/>
        {registering && <>
          <div className="password-meter" role="meter" aria-label="Password strength" aria-valuemin={0} aria-valuemax={4} aria-valuenow={strength.score}><span style={{width:`${strength.valid?100:strength.score*20}%`}}/></div>
          <p className="password-rating" role="status">Strength: <strong>{strength.label}</strong></p>
          <label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" type="password" value={confirmation} onChange={e=>setConfirmation(e.target.value)} maxLength={128} autoComplete="new-password" required disabled={busy}/>
          <ul id="password-checks" className="password-checklist" aria-label="Password requirements">{passwordChecks.map(check=><li key={check.id} data-passed={check.passed}><span aria-hidden="true">{check.passed?'✓':'○'}</span><span>{check.label}<span className="sr-only">: {check.passed?'passed':'not passed'}</span></span></li>)}</ul>
          {configError&&<><ErrorMessage message={configError}/><button type="button" className="secondary" onClick={()=>setConfigRetry(value=>value+1)}>Retry setup check</button></>}
          {!configuration&&!configError&&<p role="status" className="field-hint">Loading registration protection…</p>}
          {human&&!human.ready&&<p className="field-hint" role="status">Registration is waiting for human-verification setup. Existing accounts can still sign in.</p>}
          {human?.ready&&<>{human.mode==='test'&&<p className="error">Local test verification only — this does not establish that a visitor is human.</p>}<HumanVerification siteKey={human.site_key} onToken={setHumanToken} resetVersion={resetVersion}/></>}
        </>}
        <ErrorMessage message={error || notice}/><button className="primary" id="auth-submit" type="submit" disabled={busy||!ready}>{busy ? 'Please wait…' : registering ? 'Create account' : 'Sign in'} <span aria-hidden="true">↗</span></button>
      </form><p className="auth-footnote">A little progress, every day.</p>
    </div></main>
  </div>;
}
