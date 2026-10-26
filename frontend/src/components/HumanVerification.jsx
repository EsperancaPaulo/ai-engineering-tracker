import React,{useEffect,useRef,useState} from 'react';
let loader;
function loadTurnstile(){
 if(window.turnstile)return Promise.resolve(window.turnstile);
 if(!loader){loader=new Promise((resolve,reject)=>{
  const script=document.createElement('script');script.src='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';script.async=true;
  script.onload=()=>window.turnstile?resolve(window.turnstile):reject(new Error('Verification did not load.'));
  script.onerror=()=>{script.remove();reject(new Error('Verification could not load. Check your connection or content blocker.'));};document.head.append(script);
 }).catch(error=>{loader=null;throw error;});}
 return loader;
}
export default function HumanVerification({siteKey,onToken,resetVersion=0}){
 const container=useRef(null),callback=useRef(onToken);callback.current=onToken;
 const [error,setError]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{
  let active=true,widget,service;setError('');callback.current('');
  loadTurnstile().then(api=>{
   if(!active)return;service=api;
   widget=api.render(container.current,{sitekey:siteKey,action:'register',theme:'light',size:'flexible',
    callback:token=>{if(active){setError('');callback.current(token);}},
    'expired-callback':()=>{if(active){callback.current('');setError('Verification expired. Please complete it again.');}},
    'error-callback':()=>{if(active){callback.current('');setError('Verification could not finish. Please retry.');}},
   });
  }).catch(error=>{if(active)setError(error.message);});
  return ()=>{active=false;if(widget!==undefined)service.remove(widget);};
 },[siteKey,resetVersion,retry]);
 return <div className="human-check"><p className="field-hint">Verify you’re human</p><div ref={container}/>{error&&<><p role="alert" className="field-hint">{error}</p><button type="button" className="secondary" onClick={()=>setRetry(value=>value+1)}>Retry verification</button></>}</div>;
}
