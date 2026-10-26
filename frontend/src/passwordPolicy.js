import policy from '../../shared/password-policy.json';
export {policy};
export function assessPassword(password,name,email,estimator) {
  const length=Array.from(password).length;
  if(!length)return {valid:false,score:0,message:'Use a long, original passphrase.'};
  if(length<policy.minimum_length||length>policy.maximum_length)return {valid:false,score:0,message:'Use between 15 and 128 characters.'};
  const normalized=password.normalize('NFKC').toLowerCase(),letters=normalized.replace(/[^\p{L}]/gu,'');
  const roots=[...policy.common_roots,name.replaceAll(' ','').toLowerCase(),email.split('@')[0].toLowerCase()];
  if(roots.some(root=>root&&letters&&letters.split(root).join('')===''))return {valid:false,score:0,message:'Avoid common passwords and simple versions of your name or email.'};
  if(policy.common_phrases.includes(normalized.replace(/[^\p{L}\p{N}]/gu,'')))return {valid:false,score:0,message:'Choose an original passphrase rather than a well-known example.'};
  if(!estimator)return {valid:false,score:0,message:'Loading the local password check…'};
  const result=estimator(password,[name,email,email.split('@')[0]]);
  return {valid:result.score>=policy.minimum_score,score:result.score,message:result.score>=policy.minimum_score?'Good length and resistance to common guessing patterns.':'Try a longer, less predictable passphrase.'};
}
