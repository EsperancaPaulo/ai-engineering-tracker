import {it,expect,vi} from 'vitest';
import {createApi,jsonOptions} from '../api.js';
it('sends tokens through headers and accepts an empty 204 response', async()=>{
 const fetch=vi.fn().mockResolvedValue(new Response(null,{status:204}));vi.stubGlobal('fetch',fetch);
 expect(await createApi('temporary-test-token')('/api/tasks/1',{method:'DELETE'})).toBe(null);
 expect(fetch.mock.calls[0][0]).toBe('/api/tasks/1');expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer temporary-test-token');expect(fetch.mock.calls[0][1].cache).toBe('no-store');
});
it('ends authenticated sessions on 401',async()=>{
 const ended=vi.fn();vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({detail:'Invalid credentials'},{status:401})));
 await expect(createApi('temporary-test-token',ended)('/me')).rejects.toMatchObject({status:401});expect(ended).toHaveBeenCalledOnce();
});
it('hides server internals and reports connection errors',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(Response.json({detail:'private database detail'},{status:500})).mockRejectedValueOnce(new Error('socket error')));
 await expect(createApi()('/api/projects')).rejects.toThrow('Your workspace could not be reached.');
 await expect(createApi()('/api/projects')).rejects.toThrow('Unable to connect.');
});
it('does not invent authentication headers for public requests',async()=>{
 const fetch=vi.fn().mockResolvedValue(Response.json({id:1}));vi.stubGlobal('fetch',fetch);
 await createApi()('/auth/register',jsonOptions({name:'Test',email:'test@example.com',password:'test-only-passphrase'}));
 expect(fetch.mock.calls[0][1].headers.Authorization).toBeUndefined();expect(JSON.parse(fetch.mock.calls[0][1].body).email).toBe('test@example.com');
});
