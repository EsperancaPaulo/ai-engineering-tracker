import React from 'react';
import {act,render,screen,waitFor} from '@testing-library/react';
import {expect,it,vi} from 'vitest';
import HumanVerification from '../components/HumanVerification.jsx';
it('only forwards provider tokens, clears expired/failed checks, and cleans up the widget',async()=>{
 let callbacks;const remove=vi.fn(),renderWidget=vi.fn((container,options)=>{callbacks=options;return 'fixture-widget';});
 vi.stubGlobal('turnstile',{render:renderWidget,remove});const token=vi.fn();
 const {unmount}=render(<HumanVerification siteKey="fixture-public-key" onToken={token}/>);
 await waitFor(()=>expect(renderWidget).toHaveBeenCalledOnce());expect(token).toHaveBeenLastCalledWith('');expect(callbacks.action).toBe('register');
 act(()=>callbacks.callback('provider-response-token'));expect(token).toHaveBeenLastCalledWith('provider-response-token');
 act(()=>callbacks['expired-callback']());expect(token).toHaveBeenLastCalledWith('');expect(screen.getByRole('alert').textContent).toContain('expired');
 act(()=>callbacks['error-callback']());expect(token).toHaveBeenLastCalledWith('');expect(screen.getByRole('alert').textContent).toContain('could not finish');
 unmount();expect(remove).toHaveBeenCalledWith('fixture-widget');
});
