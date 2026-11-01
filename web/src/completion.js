export function needsCompletion(data) {
  return !data.business || data.business.status!=='ready' || !data.snapshot ||
    !Array.isArray(data.trajectory?.rows) || !data.trajectory.rows.length || (!data.research&&!data.research_availability);
}

export function createCompanyCompletion({api,onJob,onData,onNotice,isCurrent,delay=ms=>new Promise(resolve=>setTimeout(resolve,ms))}) {
  const pending=new Map();
  return function ensureComplete(data) {
    const ticker=data.ticker;
    if(!needsCompletion(data))return Promise.resolve();
    if(pending.has(ticker))return pending.get(ticker);
    const run=(async()=>{
      try {
        const result=await api(`/api/company/${encodeURIComponent(ticker)}/complete`,{method:'POST',body:'{}'});
        if(result.research_job)onJob(result.research_job);
        if(result.context_pending){
          let version=JSON.stringify([data.business,data.snapshot?.fetched_at,data.trajectory?.generated_at]);
          for(let attempt=0;attempt<120;attempt++){
            const saved=await api(`/api/company/${encodeURIComponent(ticker)}`);
            const nextVersion=JSON.stringify([saved.business,saved.snapshot?.fetched_at,saved.trajectory?.generated_at]);
            if(nextVersion!==version&&isCurrent(ticker))onData(saved);
            version=nextVersion;
            if(!saved.context_pending)break;
            await delay(1000);
          }
        }
      } catch {
        if(isCurrent(ticker))onNotice(ticker);
      } finally {pending.delete(ticker);}
    })();
    pending.set(ticker,run);
    return run;
  };
}
