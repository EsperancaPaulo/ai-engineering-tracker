import {afterEach, vi} from 'vitest';
import {cleanup} from '@testing-library/react';
Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.open=true;}});
Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function(){this.open=false;}});
afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.useRealTimers();});
