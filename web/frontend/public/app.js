const money = cents => `₱${(cents / 100).toFixed(2)}`;
const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
document.querySelectorAll('.main-nav a[href], .staff-nav a[href]').forEach(link => {
  const linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/$/, '') || '/';
  const matches = linkPath === currentPath || (linkPath !== '/' && currentPath.startsWith(`${linkPath}/`));
  if (matches) link.setAttribute('aria-current', 'page');
});
document.querySelectorAll('input[name=small],input[name=large],input[name=price]').forEach(input => input.max = '9999.99');
let category = 'all';
const search = document.querySelector('#menu-search');
function filterMenu() {
  const value = (search?.value || '').trim().toLowerCase();
  let count = 0;
  document.querySelectorAll('.product-card').forEach(card => {
    const visible = (category === 'all' || card.dataset.category === category) && card.dataset.search.includes(value);
    card.hidden = !visible; if (visible) count++;
  });
  const empty = document.querySelector('#menu-empty'); if (empty) empty.hidden = count > 0;
}
search?.addEventListener('input', filterMenu);
document.querySelectorAll('button.category-tab').forEach(button => button.addEventListener('click', () => {
  category = button.dataset.category;
  document.querySelectorAll('button.category-tab').forEach(tab => { const active = tab === button; tab.classList.toggle('selected', active); tab.setAttribute('aria-pressed', String(active)); });
  filterMenu();
}));
document.querySelectorAll('.drink-form').forEach(form => {
  function price() {
    let total = Number(form.querySelector('[name=variant_id]').selectedOptions[0]?.dataset.price || 0);
    form.querySelectorAll('[name=addon_ids]:checked').forEach(addon => total += Number(addon.dataset.price));
    total *= Number(form.querySelector('[name=quantity]').value || 1);
    form.querySelector('.drink-total').textContent = money(total);
  }
  form.addEventListener('input', price); form.addEventListener('change', price); price();
});
let submitting = false;
window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); });
document.addEventListener('submit', event => {
  const form = event.target;
  if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) { event.preventDefault(); return; }
  submitting = true;
  form.querySelectorAll('button[type=submit]').forEach(button => { button.disabled = true; });
});
document.querySelector('[data-back]')?.addEventListener('click', () => window.history.length > 1 ? window.history.back() : window.location.assign('/'));

let audio, soundEnabled = false;
document.querySelector('#enable-sound')?.addEventListener('click', async event => {
  try {
    audio ||= new (window.AudioContext || window.webkitAudioContext)();
    await audio.resume(); soundEnabled = !soundEnabled;
    event.target.textContent = soundEnabled ? 'Order sound enabled' : 'Enable order sound';
  } catch { event.target.textContent = 'Sound unavailable'; }
});
function beep() {
  if (!soundEnabled || !audio) return;
  const oscillator = audio.createOscillator(), gain = audio.createGain();
  oscillator.frequency.value = 880; gain.gain.value = 0.12;
  oscillator.connect(gain); gain.connect(audio.destination);
  oscillator.start(); oscillator.stop(audio.currentTime + 0.15);
}
let pane = document.querySelector('[data-poll]');
let lastEvent = pane?.dataset.eventId;
function sync(message, offline) {
  document.querySelectorAll('.sync-status').forEach(label => { label.textContent = message; label.classList.toggle('offline', offline); });
  pane?.querySelectorAll('button[type=submit]').forEach(button => { button.disabled = offline; });
}
async function poll() {
  if (!pane || submitting) return;
  try {
    const response = await fetch(window.location.href, { cache: 'no-store', headers: { 'X-Refresh': '1' }, signal: AbortSignal.timeout(5000) });
    if (response.redirected && response.url.includes('/login')) { window.location.assign('/login'); return; }
    if (!response.ok) throw new Error('Refresh failed');
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    const fresh = doc.getElementById(pane.id); if (!fresh) throw new Error('Missing order data');
    const event = fresh.dataset.eventId;
    if (event && lastEvent !== undefined && event !== lastEvent) beep();
    if (event) lastEvent = event;
    pane.innerHTML = fresh.innerHTML; if (event) pane.dataset.eventId = event;
    sync('Updated just now · refreshes every 3 seconds', false);
  } catch { sync('Connection lost · displayed orders may be outdated', true); }
  if (!submitting) setTimeout(poll, 3000);
}
if (pane) { sync('Connecting…', false); setTimeout(poll, 3000); }
