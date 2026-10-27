import React from 'react';
export default function AutomationPreview({effect,priority='medium',aiOverride=false}){
 if(!effect)return null;
 return <section className="automation-result" aria-label={`Automation from ${effect.rule_name}`}><strong>Rule: {effect.rule_name}</strong><p>Priority: {aiOverride?'approved AI priority':effect.priority||priority} · Assigned to: {effect.assignee_name||'you'}</p>{effect.checklist.length>0&&<><p>Checklist to add:</p><ul>{effect.checklist.map(line=><li key={line}>{line}</li>)}</ul></>}</section>;
}
