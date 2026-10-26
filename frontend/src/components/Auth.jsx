import React, {useState} from 'react';
import {createApi, jsonOptions} from '../api.js';
import {Brand, ErrorMessage} from './Shared.jsx';
const api = createApi();

export default function Auth({onSignIn, notice = ''}) {
  const [mode, setMode] = useState('login');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const registering = mode === 'register';
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const form = event.currentTarget;
    const values = new FormData(form), email = values.get('email').trim(), password = values.get('password');
    try {
      if (registering) await api('/auth/register', jsonOptions({name: values.get('name').trim(), email, password}));
      const data = await api('/auth/login', {method: 'POST', body: new URLSearchParams({username: email, password})});
      const user = await createApi(data.access_token)('/me');
      form.reset();
      onSignIn({token: data.access_token, user, expiresAt: Date.now() + data.expires_in * 1000});
    } catch (error) {setError(error.message);} finally {setBusy(false);}
  }
  return <div className="auth-layout" id="auth-view">
    <section className="intro"><Brand/><div className="intro-copy"><span className="eyebrow">SMALL STEPS. REAL PROGRESS.</span><h1>Build skills.<br/>Ship projects.<br/><em>See your growth.</em></h1><p>A focused workspace for your journey in AI engineering. Turn ambitious ideas into your next completed task.</p><div className="intro-note"><span className="signal"/> Your next chapter starts with one small step.</div></div><footer>Made for the work that moves you forward.<span>01 / YOUR WORKSPACE</span></footer></section>
    <main className="auth-panel"><div className="auth-card"><span className="eyebrow">LET’S GET BUILDING</span><h2>{registering ? 'Start your next chapter.' : 'Welcome back.'}</h2><p>{registering ? 'Create a workspace for your progress.' : 'Sign in and pick up where you left off.'}</p>
      <div className="auth-tabs" role="group" aria-label="Choose account action">{[['login','Sign in'],['register','Create account']].map(([value,label]) => <button key={value} type="button" disabled={busy} aria-pressed={mode === value} className={mode === value ? 'selected' : ''} onClick={() => {setMode(value); setError('');}}>{label}</button>)}</div>
      <form id="auth-form" onSubmit={submit}>
        {registering && <><label htmlFor="name">Your name</label><input id="name" name="name" autoComplete="name" maxLength={100} required disabled={busy}/></>}
        <label htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete="username" placeholder="you@example.com" maxLength={255} required disabled={busy}/>
        <label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete={registering ? 'new-password' : 'current-password'} minLength={registering ? 15 : 1} maxLength={128} required disabled={busy}/>
        {registering && <p className="field-hint">Use 15–128 characters. A long, unique passphrase works well.</p>}
        <ErrorMessage message={error || notice}/><button className="primary" id="auth-submit" type="submit" disabled={busy}>{busy ? 'Please wait…' : registering ? 'Create account' : 'Sign in'} <span aria-hidden="true">↗</span></button>
      </form><p className="auth-footnote">A little progress, every day.</p>
    </div></main>
  </div>;
}
