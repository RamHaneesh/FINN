const HISTORY_KEY = 'finn.recent-searches.v1';
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalize = value => String(value).toLowerCase().replace(/\.ns$/,'').replace(/[^a-z0-9&]+/g,' ').trim();
const validTicker = value => typeof value === 'string' && /^[A-Z0-9][A-Z0-9&-]{0,24}$/.test(value);

export function createTickerSearch({api, onChoose}) {
  const input = document.querySelector('#ticker-input');
  const container = document.querySelector('.search-container');
  const popup = document.querySelector('#search-suggestions');
  const list = document.querySelector('#ticker-suggestions');
  const heading = document.querySelector('#suggestion-heading');
  const note = document.querySelector('#suggestion-note');
  const clear = document.querySelector('#clear-search-history');
  const recentRow = document.querySelector('#recent-searches');
  let directory = [], complete = false, loading, retries = 0, matches = [], selected = -1;
  let recent = [];
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    if (Array.isArray(saved)) recent = saved.filter(item => item && validTicker(item.ticker) && typeof item.name === 'string').slice(0,8);
  } catch { /* Private mode/storage restrictions should not break search. */ }

  function persist() {
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(recent)); } catch { /* Keep session history usable. */ }
  }
  function close() {
    popup.hidden = true;
    input.setAttribute('aria-expanded','false');
    input.removeAttribute('aria-activedescendant');
    selected = -1;
  }
  function choose(item) {
    input.value = item.ticker;
    close();
    input.blur();
    onChoose(item.ticker);
  }
  function renderRecent() {
    recentRow.hidden = !recent.length;
    recentRow.innerHTML = recent.length ? `<span class="recent-label">Recent</span>${recent.slice(0,4).map(item => `<button type="button" data-recent="${escape(item.ticker)}" title="${escape(item.name)}">${escape(item.ticker)}</button>`).join('')}` : '';
    recentRow.querySelectorAll('[data-recent]').forEach(button => button.onclick = () => choose(recent.find(item => item.ticker === button.dataset.recent)));
  }
  function ranked(query) {
    const q = normalize(query);
    if (!q) return recent.length ? recent : directory.slice(0,6);
    const words = q.split(/\s+/);
    return directory.map(item => {
      const ticker = normalize(item.ticker), name = normalize(item.name);
      const score = ticker === q ? 0 : ticker.startsWith(q) ? 1 : name.startsWith(q) ? 2 : words.every(word => `${ticker} ${name}`.includes(word)) ? 3 : 99;
      return {item, score};
    }).filter(result => result.score < 99).sort((a,b) => a.score-b.score || a.item.ticker.localeCompare(b.item.ticker)).slice(0,8).map(result => result.item);
  }
  function highlight(text) {
    const query = input.value.trim().replace(/\.NS$/i,'');
    const at = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1;
    return at < 0 ? escape(text) : `${escape(text.slice(0,at))}<mark>${escape(text.slice(at,at+query.length))}</mark>${escape(text.slice(at+query.length))}`;
  }
  function render() {
    selected = -1;
    matches = ranked(input.value);
    const isRecent = !input.value.trim() && recent.length > 0;
    heading.textContent = isRecent ? 'Recent searches' : input.value.trim() ? 'Matching companies' : 'NSE companies';
    clear.hidden = !isRecent;
    list.innerHTML = matches.map((item,index) => `<button type="button" role="option" id="ticker-option-${index}" aria-selected="false" class="ticker-option" data-option="${index}"><span class="suggestion-symbol">${highlight(item.ticker)}</span><span class="suggestion-name">${highlight(item.name)}</span><span class="suggestion-exchange">NSE</span></button>`).join('');
    list.querySelectorAll('[data-option]').forEach(button => button.onclick = () => choose(matches[Number(button.dataset.option)]));
    note.textContent = matches.length ? (!complete ? 'Showing saved companies. Any NSE ticker can still be entered.' : 'Tap a company, or use ↑ ↓ and Enter.') : 'No suggestions. You can still enter an exact NSE ticker.';
    popup.hidden = false;
    input.setAttribute('aria-expanded','true');
    input.removeAttribute('aria-activedescendant');
  }
  async function loadDirectory() {
    if (loading) return loading;
    loading = api('/api/symbols').then(data => {
      directory = data.symbols.filter(item => validTicker(item.ticker) && typeof item.name === 'string');
      complete = data.complete;
      if (document.activeElement === input) render();
      if (!complete && retries++ < 2) setTimeout(() => { loading = null; if (document.activeElement === input) loadDirectory(); }, 3000);
    }).catch(() => { directory = recent; loading = null; });
    return loading;
  }
  input.addEventListener('focus', () => { input.select(); render(); loadDirectory(); });
  input.addEventListener('input', render);
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') { close(); return; }
    if (['ArrowDown','ArrowUp'].includes(event.key)) {
      event.preventDefault();
      if (popup.hidden) render();
      if (!matches.length) return;
      selected = selected < 0 ? (event.key === 'ArrowDown' ? 0 : matches.length-1) : (selected + (event.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length;
      list.querySelectorAll('[role="option"]').forEach((button,index) => button.setAttribute('aria-selected', String(index === selected)));
      const active = document.querySelector(`#ticker-option-${selected}`);
      input.setAttribute('aria-activedescendant',active.id);
      active.scrollIntoView({block:'nearest'});
    } else if (event.key === 'Enter' && !popup.hidden && selected >= 0) {
      event.preventDefault(); choose(matches[selected]);
    }
  });
  container.addEventListener('focusout', event => { if (!container.contains(event.relatedTarget)) close(); });
  document.addEventListener('pointerdown', event => { if (!container.contains(event.target)) close(); });
  clear.onclick = () => { recent = []; persist(); renderRecent(); render(); input.focus(); };
  window.addEventListener('storage', event => {
    if (event.key !== HISTORY_KEY) return;
    try { const value = JSON.parse(event.newValue || '[]'); recent = Array.isArray(value) ? value.filter(item => item && validTicker(item.ticker) && typeof item.name === 'string').slice(0,8) : []; renderRecent(); } catch { /* Ignore invalid storage. */ }
  });
  renderRecent();
  return {
    close,
    reset() { input.value = ''; close(); },
    resolve() { if(!input.value.trim())return ''; const exact = input.value.trim().toUpperCase().replace(/\.NS$/,''); return directory.find(item => item.ticker === exact)?.ticker || ranked(input.value)[0]?.ticker || exact; },
    remember(data) {
      const known = directory.find(item => item.ticker === data.ticker);
      if (!validTicker(data.ticker) || (!data.snapshot && !data.research && !known)) return;
      const name = data.name && data.name !== data.ticker ? data.name : known?.name || data.ticker;
      recent = [{ticker:data.ticker,name}, ...recent.filter(item => item.ticker !== data.ticker)].slice(0,8);
      persist(); renderRecent();
    }
  };
}
