import policy from '../../shared/password-policy.json';
export {policy};
export function assessPassword(password,name,email,estimator) {
  const length=Array.from(password).length;
  const normalized=password.normalize('NFKC').toLowerCase(),letters=normalized.replace(/[^\p{L}]/gu,'');
  const repeatsRoot=root=>Boolean(root&&letters&&letters.split(root).join('')==='');
  const common=policy.common_roots.some(repeatsRoot)||policy.common_phrases.includes(normalized.replace(/[^\p{L}\p{N}]/gu,''));
  const personal=[name.replaceAll(' ','').toLowerCase(),email.split('@')[0].toLowerCase()].some(repeatsRoot);
  const withinLength=length>=policy.minimum_length&&length<=policy.maximum_length;
  const result=estimator&&length&&length<=policy.maximum_length?estimator(password,[name,email,email.split('@')[0]]):null;
  const checks=[
    {id:'length',label:`${policy.minimum_length}–${policy.maximum_length} characters`,passed:withinLength},
    {id:'common',label:'Not a common password or known example',passed:Boolean(length)&&!common},
    {id:'personal',label:'Not a simple version of your name or email',passed:Boolean(length)&&!personal},
    {id:'guessing',label:'Passes the strength check',passed:Boolean(result&&result.score>=policy.minimum_score)},
  ];
  const valid=checks.every(check=>check.passed),score=result?.score??0;
  return {valid,score,checks,label:!length?'Not checked':!estimator?'Checking…':valid?'Strong':score>=2&&withinLength&&!common&&!personal?'Fair':'Weak'};
}
