const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const active = job => ['queued','running'].includes(job.status);
function duration(seconds) { seconds=Math.max(0,Math.round(seconds));return seconds<60?`${seconds}s`:`${Math.floor(seconds/60)}m${seconds%60?` ${seconds%60}s`:''}`; }

export function createAnalysisProgress({api,onSnapshot,onComplete,onOpen,onRetry}) {
  const jobs=new Map();
  const card=document.querySelector('#analysis-progress');
  const background=document.querySelector('#background-analysis');
  let ticker=null;

  function latest(symbol) { return [...jobs.values()].filter(record=>record.job.ticker===symbol).sort((a,b)=>Number(active(b.job))-Number(active(a.job))||b.job.created_at.localeCompare(a.job.created_at))[0]; }
  function elapsed(record) {return (record.job.progress?.elapsed_seconds||0)+(active(record.job)?Math.floor((Date.now()-record.received)/1000):0);}
  function syncButtons() {
    const record=latest(ticker), busy=record&&active(record.job);
    for(const id of ['start-research','rerun-research']) {
      const button=document.getElementById(id);
      if(!button)continue;
      if(!button.dataset.idleText)button.dataset.idleText=button.textContent;
      button.disabled=!!busy;
      button.setAttribute('aria-busy',String(!!busy));
      button.textContent=busy?(record.job.status==='queued'?'Analysis queued…':'Analysis in progress…'):button.dataset.idleText;
    }
  }
  function render() {
    const record=latest(ticker);
    card.hidden=!record||record.job.status==='completed';
    if(card.hidden)card.replaceChildren();
    if(record&&record.job.status!=='completed') {
      const job=record.job, p=job.progress||{}, running=active(job), step=p.step||0;
      const value=elapsed(record);
      const ahead=p.queue_ahead||0;
      let time='';
      if(job.status==='queued')time=p.worker_available?(ahead?`${ahead} ${ahead===1?'request':'requests'} ahead of yours`:'Your request is ready to start.'):'Waiting for the analysis service. Your request is saved.';
      else if(job.status==='running')time=`Stage ${step} of ${p.total_steps||5}`;
      else time=job.status==='completed'?'Saved locally. Future visits open the saved view.':'Previous saved research is still available.';
      const title=record.connectionError?'Reconnecting to analysis…':p.title||'Analysis queued';
      let detail=p.detail||'Your request is saved and will be processed in the background.';
      if(job.status==='failed'&&/Gemini|ValidationError/.test(detail))detail=/429/.test(detail)?'The analysis service reached its current quota or rate limit. Please try again later.':'The analysis service could not return usable evidence. You can retry without losing saved research.';
      const state=job.status==='failed'?'failed':job.status==='completed'?'complete':'working';
      card.className=`analysis-progress ${state}`;
      card.setAttribute('aria-busy',String(!!running));
      card.dataset.jobId=job.id;
      card.innerHTML=`<div class="analysis-heading"><h3>${running?'<span class="analysis-pulse"></span>Extracting guidance from primary transcripts…':escape(title)}</h3><span class="analysis-state">${job.status==='queued'?'QUEUED':running?'PROCESSING':'NEEDS ATTENTION'}</span></div><p class="analysis-detail">${escape(detail)}</p><div class="analysis-timing"><span id="analysis-elapsed">${job.status==='queued'?'Queued':'Elapsed'} ${duration(value)}</span><span id="analysis-stage-status">${escape(time)}</span></div>${job.status==='failed'?'<button type="button" class="button secondary" id="retry-analysis">Retry analysis</button>':''}`;
      document.querySelector('#retry-analysis')?.addEventListener('click',()=>onRetry(job.ticker));
    }
    const awaiting=document.querySelector('#narrative-awaiting');if(awaiting)awaiting.hidden=!!record;
    const pending=[...jobs.values()].filter(record=>active(record.job));
    background.hidden=!pending.length||(!document.querySelector('#view-research').hidden&&!!record&&active(record.job));
    if(pending.length) {
      const record=pending.find(record=>record.job.status==='running')||pending[0];
      background.innerHTML=`<span class="analysis-pulse"></span><span>${escape(record.job.ticker)} · ${escape(record.connectionError?'Reconnecting':record.job.progress?.title||'Analysis queued')}${pending.length>1?` · ${pending.length} requests`:''}</span><span>View →</span>`;
      background.onclick=()=>onOpen(record.job.ticker);
    }
    syncButtons();
  }
  async function poll(id) {
    const record=jobs.get(id);
    if(!record||record.polling||!active(record.job))return;
    record.polling=true;
    let delay=document.hidden?5000:1500;
    try {
      const previous=record.job;
      const job=await api(`/api/jobs/${id}`);
      record.job=job;record.received=Date.now();record.connectionError=false;record.failures=0;
      render();
      if(ticker===job.ticker&&(previous.stage.split(':')[0]!==job.stage.split(':')[0]||job.status==='completed'))await onSnapshot(job.ticker);
      if(job.status==='completed')onComplete?.(job.ticker);
    } catch {
      record.connectionError=true;
      record.failures=(record.failures||0)+1;
      delay=Math.min(15000,1500*2**Math.min(record.failures,4));
      render();
    } finally {
      record.polling=false;
      if(active(record.job))record.timer=setTimeout(()=>poll(id),delay);
    }
  }
  function track(job) {
    if(!job)return;
    let record=jobs.get(job.id);
    if(record) {record.job=job;record.received=Date.now();}
    else {record={job,received:Date.now(),polling:false};jobs.set(job.id,record);}
    render();
    if(active(job)&&!record.timer&&!record.polling)poll(job.id);
  }
  setInterval(()=>{
    // Update the clock without rebuilding the card or stealing keyboard focus.
    const record=latest(ticker);
    if(!record||!active(record.job))return;
    const clock=document.querySelector('#analysis-elapsed');
    if(clock)clock.textContent=`${record.job.status==='queued'?'Queued':'Elapsed'} ${duration(elapsed(record))}`;
  },1000);
  return {
    track, syncButtons,
    mount(target) {target.appendChild(card);render();},
    select(symbol) {ticker=symbol;render();},
    clearSelection() {ticker=null;render();},
    isActive(symbol) {const record=latest(symbol);return !!record&&active(record.job);},
    async restore() {try {const data=await api('/api/research/active');data.jobs.forEach(track);}catch {/* Existing saved views remain available. */}}
  };
}
