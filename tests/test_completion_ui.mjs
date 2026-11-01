import assert from 'node:assert/strict';
import {createCompanyCompletion,needsCompletion} from '../web/src/completion.js';

const full={ticker:'TEST',business:{status:'ready'},snapshot:{fetched_at:'today'},trajectory:{rows:[{}]},research:{narratives:[]}};
assert.equal(needsCompletion(full),false);
for(const field of ['business','snapshot','trajectory','research'])assert.equal(needsCompletion({...full,[field]:null}),true);
let posts=0,loads=0,jobs=0,renders=0;
let release;
const gate=new Promise(resolve=>release=resolve);
const ensure=createCompanyCompletion({
  api:async(path)=>{
    if(path.endsWith('/complete')){posts++;await gate;return {context_pending:true,research_job:{id:'one'}};}
    loads++;return {...full,context_pending:false};
  },
  onJob:()=>jobs++,onData:()=>renders++,onNotice:()=>assert.fail('Unexpected error'),isCurrent:()=>true,delay:async()=>{}
});
await ensure(full);
assert.equal(posts,0);
const missing={...full,snapshot:null,research:null};
const first=ensure(missing),duplicate=ensure(missing);
assert.equal(first,duplicate);
release();await first;
assert.equal(posts,1);assert.equal(loads,1);assert.equal(jobs,1);assert.equal(renders,1);
let staleRenders=0;
const other=createCompanyCompletion({api:async path=>path.endsWith('/complete')?{context_pending:true}:full,onJob(){},onData:()=>staleRenders++,onNotice(){},isCurrent:()=>false,delay:async()=>{}});
await other(missing);
assert.equal(staleRenders,0);
console.log('Automatic completion: missing sections, completed-empty research, duplicate suppression and stale responses verified.');
