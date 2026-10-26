import {expect,it} from 'vitest';
import zxcvbn from 'zxcvbn';
import {assessPassword} from '../passwordPolicy.js';
it.each(['Password123456789!','qwertyuiopasdfghjkl','correct horse battery staple','11111111111111111111','TestOwner123456789!'])('rejects predictable password %s',password=>{
 expect(assessPassword(password,'Test Owner','test@example.com',zxcvbn).valid).toBe(false);
});
it('accepts an original long passphrase without composition requirements',()=>{
 expect(assessPassword('cobalt lanterns drift beyond seven orchards','','',zxcvbn).valid).toBe(true);
});
it('never marks a short or unchecked password as ready',()=>{
 expect(assessPassword('short','','',zxcvbn).valid).toBe(false);
 expect(assessPassword('cobalt lanterns drift beyond seven orchards','','',null).valid).toBe(false);
});
