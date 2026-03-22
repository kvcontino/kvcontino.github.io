// js/filters.js — filter UI components

import { state, setState, bus } from './state.js';

let regions, stateNames;

export function initFilters(geoData, pops) {
  regions    = geoData;
  stateNames = geoData.stateNames;

  // ── Metric tabs ───────────────────────────────────────────────────────────
  document.querySelectorAll('.metric-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.metric-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const metric = btn.dataset.metric;
      setState({ metric }, 'metricChanged');
      updateFilterVisibility(metric);
    });
  });

  // ── Enrollment type ───────────────────────────────────────────────────────
  const enrollType = document.getElementById('enrollment-type');
  enrollType.addEventListener('change', () => {
    setState({ enrollmentField: enrollType.value }, 'filterChanged');
  });

  // ── Geo filter — custom multi-select ──────────────────────────────────────
  buildGeoDropdown(geoData);

  // ── PMPM category ─────────────────────────────────────────────────────────
  const pmpmCat = document.getElementById('pmpm-category');
  pmpmCat.addEventListener('change', () => {
    setState({ pmpmCategory: pmpmCat.value }, 'filterChanged');
  });

  // ── Per-capita toggle ─────────────────────────────────────────────────────
  document.querySelectorAll('.toggle-btn[data-value]').forEach(btn => {
    btn.addEventListener('click', () => {
      const val = btn.dataset.value;
      document.querySelectorAll('.toggle-btn[data-value]').forEach(b => {
        b.classList.toggle('active', b.dataset.value === val);
      });
      if (val === 'per_capita' || val === 'absolute') {
        setState({ perCapita: val === 'per_capita' }, 'filterChanged');
      }
    });
  });

  // ── Date selectors ────────────────────────────────────────────────────────
  document.getElementById('snapshot-date').addEventListener('change', e => {
    setState({ snapshotPeriod: e.target.value }, 'filterChanged');
  });
  document.getElementById('change-start-date').addEventListener('change', e => {
    setState({ changeStartPeriod: e.target.value }, 'filterChanged');
  });
  document.getElementById('change-end-date').addEventListener('change', e => {
    setState({ changeEndPeriod: e.target.value }, 'filterChanged');
  });
}

export function populatePeriodSelectors(periods) {
  const fmt = p => {
    const y = p.slice(0, 4), m = p.slice(4, 6);
    return new Date(+y, +m - 1).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  };

  const snapSel    = document.getElementById('snapshot-date');
  const startSel   = document.getElementById('change-start-date');
  const endSel     = document.getElementById('change-end-date');

  // Most recent first for snapshot
  const reversed = [...periods].reverse();
  snapSel.innerHTML = reversed.map(p => `<option value="${p}">${fmt(p)}</option>`).join('');

  // Chronological for start/end
  startSel.innerHTML = periods.map(p => `<option value="${p}">${fmt(p)}</option>`).join('');
  endSel.innerHTML   = reversed.map(p => `<option value="${p}">${fmt(p)}</option>`).join('');

  // Defaults: snapshot = latest; change = 24 months ago → latest
  snapSel.value  = periods[periods.length - 1];
  endSel.value   = periods[periods.length - 1];

  const defaultStartIdx = Math.max(0, periods.length - 25);
  startSel.value = periods[defaultStartIdx];

  setState({
    snapshotPeriod:    periods[periods.length - 1],
    changeStartPeriod: periods[defaultStartIdx],
    changeEndPeriod:   periods[periods.length - 1]
  });
}

export function populatePMPMCategories(categories) {
  const sel = document.getElementById('pmpm-category');
  sel.innerHTML = categories.map(c =>
    `<option value="${c}">${c.charAt(0).toUpperCase() + c.slice(1)}</option>`
  ).join('');
}

function updateFilterVisibility(metric) {
  const enrollGroup  = document.getElementById('enrollment-type-group');
  const pmpmGroup    = document.getElementById('pmpm-category-group');
  const normToggle   = document.getElementById('trend-normalize-toggle');
  const snapCapBtn   = document.getElementById('snap-cap-btn');
  const snapAbsBtn   = document.getElementById('snap-abs-btn');

  enrollGroup.style.display  = metric === 'pmpm' ? 'none' : '';
  pmpmGroup.style.display    = metric === 'pmpm' ? '' : 'none';
  normToggle.style.display   = metric === 'enrollment' ? '' : 'none';

  // Per-capita only meaningful for enrollment and managed care count
  if (snapCapBtn) {
    snapCapBtn.style.display = metric === 'enrollment' ? '' : 'none';
    snapAbsBtn?.click(); // reset to absolute
  }
}

// ── Geo dropdown (custom) ─────────────────────────────────────────────────────
function buildGeoDropdown(geoData) {
  const container = document.getElementById('geo-filter-container');
  if (!container) return;

  container.innerHTML = `
    <div class="geo-dropdown" id="geo-dropdown">
      <button class="geo-trigger" id="geo-trigger" type="button">
        <span id="geo-label">All States</span>
        <svg width="10" height="6" viewBox="0 0 10 6"><path d="M1 1l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>
      </button>
      <div class="geo-panel hidden" id="geo-panel">
        <div class="geo-search-wrap">
          <input type="text" id="geo-search" placeholder="Search states…" autocomplete="off">
        </div>
        <div class="geo-options" id="geo-options"></div>
      </div>
    </div>`;

  buildGeoOptions(geoData);

  const trigger = document.getElementById('geo-trigger');
  const panel   = document.getElementById('geo-panel');
  const search  = document.getElementById('geo-search');

  trigger.addEventListener('click', () => {
    panel.classList.toggle('hidden');
    if (!panel.classList.contains('hidden')) search.focus();
  });

  // Close on outside click
  document.addEventListener('click', e => {
    if (!container.contains(e.target)) panel.classList.add('hidden');
  });

  search.addEventListener('input', () => filterGeoOptions(search.value));
}

function buildGeoOptions(geoData) {
  const el = document.getElementById('geo-options');
  if (!el) return;

  const REGION_COLORS = { Northeast: '#58a6ff', Midwest: '#3fb950', South: '#f78166', West: '#e3b341' };
  let html = `<div class="geo-option geo-option-all selected" data-type="all">
    <span class="geo-check">✓</span> <span>All States</span>
  </div>`;

  html += `<div class="geo-section-label">Census Regions</div>`;
  for (const [region, states] of Object.entries(geoData.regions)) {
    const color = REGION_COLORS[region] || '#888';
    html += `<div class="geo-option geo-region" data-type="region" data-value="${region}" style="--accent:${color}">
      <span class="geo-check"></span>
      <span class="geo-dot" style="background:${color}"></span>
      <span>${region}</span>
      <span class="geo-count">${states.length}</span>
    </div>`;
  }

  html += `<div class="geo-section-label">Census Divisions</div>`;
  for (const [div, states] of Object.entries(geoData.divisions)) {
    const region = geoData.divisionToRegion[div];
    const color  = REGION_COLORS[region] || '#888';
    html += `<div class="geo-option geo-division" data-type="division" data-value="${div}" style="--accent:${color}">
      <span class="geo-check"></span>
      <span class="geo-dot" style="background:${color};opacity:0.5"></span>
      <span>${div}</span>
      <span class="geo-count">${states.length}</span>
    </div>`;
  }

  // Build flat state list (all states from all regions combined, sorted by name)
  const allStates = Object.values(geoData.regions).flat();
  allStates.sort((a, b) => (geoData.stateNames[a] || a).localeCompare(geoData.stateNames[b] || b));

  html += `<div class="geo-section-label">Individual States</div>`;
  for (const abbr of allStates) {
    const region = geoData.stateToRegion[abbr];
    const color  = REGION_COLORS[region] || '#888';
    html += `<div class="geo-option geo-state" data-type="state" data-value="${abbr}" style="--accent:${color}" data-search="${(geoData.stateNames[abbr] || abbr).toLowerCase()}">
      <span class="geo-check"></span>
      <span class="geo-abbr">${abbr}</span>
      <span>${geoData.stateNames[abbr] || abbr}</span>
    </div>`;
  }

  el.innerHTML = html;

  el.addEventListener('click', e => {
    const opt = e.target.closest('.geo-option');
    if (!opt) return;
    selectGeoOption(opt, geoData);
  });
}

function selectGeoOption(opt, geoData) {
  const REGION_COLORS = { Northeast: '#58a6ff', Midwest: '#3fb950', South: '#f78166', West: '#e3b341' };
  const type  = opt.dataset.type;
  const value = opt.dataset.value;

  // Clear all
  document.querySelectorAll('.geo-option').forEach(o => {
    o.classList.remove('selected');
    o.querySelector('.geo-check').textContent = '';
  });

  opt.classList.add('selected');
  opt.querySelector('.geo-check').textContent = '✓';

  let label, states;
  if (type === 'all') {
    label = 'All States'; states = null;
  } else if (type === 'region') {
    label = value; states = new Set(geoData.regions[value]);
  } else if (type === 'division') {
    label = value; states = new Set(geoData.divisions[value]);
  } else {
    label = `${value} — ${geoData.stateNames[value] || value}`;
    states = new Set([value]);
  }

  document.getElementById('geo-label').textContent = label;
  setState({ geo: { type, label, states } }, 'filterChanged');
  document.getElementById('geo-panel').classList.add('hidden');
}

function filterGeoOptions(query) {
  const q = query.toLowerCase();
  document.querySelectorAll('.geo-option').forEach(opt => {
    if (q === '') { opt.style.display = ''; return; }
    const text = (opt.dataset.search || opt.textContent || '').toLowerCase();
    opt.style.display = text.includes(q) ? '' : 'none';
  });
  document.querySelectorAll('.geo-section-label').forEach(lbl => {
    lbl.style.display = q === '' ? '' : 'none';
  });
}
