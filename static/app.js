const byId = (id) => document.getElementById(id);

function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function setText(id, value) {
  byId(id).textContent = value ?? '—';
}

function drawChart(history) {
  const host = byId('chart');
  host.replaceChildren();
  const points = history.filter((entry) => typeof entry.item_level === 'number');
  setText('sample-count', `${points.length} ${points.length === 1 ? 'snapshot' : 'snapshots'}`);
  if (points.length < 2) {
    host.textContent = 'Refresh again later to see your progression here.';
    host.setAttribute('aria-label', 'Not enough snapshots to show a trend');
    return;
  }
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 600 160');
  const values = points.map((point) => point.item_level);
  const low = Math.min(...values) - 2;
  const high = Math.max(...values) + 2;
  const coords = values.map((value, index) => {
    const x = 12 + index * (576 / (values.length - 1));
    const y = 140 - ((value - low) / (high - low || 1)) * 120;
    return [x, y];
  });
  const guide = document.createElementNS(ns, 'line');
  for (const [key, value] of Object.entries({x1: '0', x2: '600', y1: '140', y2: '140', stroke: '#33454c'})) guide.setAttribute(key, value);
  svg.appendChild(guide);
  const line = document.createElementNS(ns, 'polyline');
  line.setAttribute('points', coords.map(([x, y]) => `${x},${y}`).join(' '));
  line.setAttribute('fill', 'none');
  line.setAttribute('stroke', '#dfb76e');
  line.setAttribute('stroke-width', '3');
  line.setAttribute('stroke-linecap', 'round');
  line.setAttribute('stroke-linejoin', 'round');
  svg.appendChild(line);
  for (const [x, y] of coords) {
    const circle = document.createElementNS(ns, 'circle');
    circle.setAttribute('cx', String(x));
    circle.setAttribute('cy', String(y));
    circle.setAttribute('r', '4');
    circle.setAttribute('fill', '#dfb76e');
    svg.appendChild(circle);
  }
  host.appendChild(svg);
  host.setAttribute('aria-label', `Item level from ${values[0]} to ${values.at(-1)} across ${values.length} snapshots`);
}

async function loadState() {
  const response = await fetch('/api/state', {cache: 'no-store'});
  if (!response.ok) throw new Error('Could not load character data');
  const state = await response.json();
  byId('demo-banner').hidden = state.mode !== 'demo';
  const current = state.latest;
  setText('level', current?.level);
  setText('item-level', current?.item_level);
  setText('class-spec', [current?.specialization, current?.class_name].filter(Boolean).join(' ') || null);
  setText('achievements', current?.achievement_points?.toLocaleString());
  setText('updated', current ? `Updated ${formatTime(current.fetched_at)}` : 'Waiting for first update');
  setText('last-success', current ? formatTime(current.fetched_at) : null);
  setText('last-attempt', state.last_attempt ? formatTime(state.last_attempt.attempted_at) : null);
  setText('status-message', state.last_attempt?.message ?? 'Waiting for first refresh');
  byId('status-dot').className = `status-dot ${state.last_attempt ? (state.last_attempt.succeeded ? 'ok' : 'error') : ''}`;
  drawChart(state.history);
}

async function refresh() {
  const button = byId('refresh');
  const notice = byId('notice');
  button.disabled = true;
  notice.className = 'notice';
  notice.textContent = 'Refreshing character…';
  try {
    const response = await fetch('/api/refresh', {method: 'POST'});
    const result = await response.json();
    notice.textContent = result.message;
    notice.classList.toggle('error', !result.ok);
    await loadState();
  } catch {
    notice.textContent = 'The tracker could not complete the refresh.';
    notice.classList.add('error');
  } finally {
    button.disabled = false;
  }
}

byId('refresh').addEventListener('click', refresh);
loadState().catch(() => {
  byId('notice').textContent = 'The tracker is unavailable. Check that the service is running.';
  byId('notice').classList.add('error');
});
