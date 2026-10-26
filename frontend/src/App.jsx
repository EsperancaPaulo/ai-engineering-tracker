import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {createApi} from './api.js';
import Auth from './components/Auth.jsx';
import Workspace from './components/Workspace.jsx';

export default function App() {
  const [session, setSession] = useState(null), [notice, setNotice] = useState(''), [toast, setToast] = useState('');
  const sessionRef = useRef(session), toastTimer = useRef(null);
  sessionRef.current = session;
  const notify = useCallback(message => {setToast(message); clearTimeout(toastTimer.current); toastTimer.current = setTimeout(() => setToast(''),4000);}, []);
  const signOut = useCallback((message = '') => {sessionRef.current = null; setSession(null); setNotice(message); setToast('');}, []);
  const api = useMemo(() => createApi(session?.token, () => {
    if (sessionRef.current?.token === session?.token) signOut('Your session has ended. Please sign in again.');
  }), [session?.token, signOut]);
  useEffect(() => {
    if (!session) return;
    const timer = setTimeout(() => signOut('Your session has ended. Please sign in again.'), Math.max(0,session.expiresAt-Date.now()));
    return () => clearTimeout(timer);
  }, [session,signOut]);
  useEffect(() => () => clearTimeout(toastTimer.current), []);
  return <>{session ? <Workspace key={session.token} user={session.user} api={api} notify={notify} onSignOut={() => signOut()}/> : <Auth notice={notice} onSignIn={value => {setNotice(''); setSession(value);}}/>}{toast && <div className="toast" role="status">{toast}</div>}</>;
}
