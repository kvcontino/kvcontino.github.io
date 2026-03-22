// filters.js — filter UI components

import { state, setState, bus } from './state.js';

let _geoData = null;

// Track multi-select state
let _selectedRegions = new Set();   // empty = all
let _selectedStates  = new Set();   // empty = all within selected regions

export function initFilters(geoData, pops) {
  _geoData = geoData;

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

  // ── PMPM category ─────────────────────────────────────────────────────────
  const pmpmCat = document.getElementById('pmpm-category');
  pmpmCat.addEventListener('change', () => {
    setState({ pmpmCategory: pmpmCat.value }, 'filterChanged');
  });

  // ── Region multi-select ───────────────────────────────────────────────────
  buildMultiSelect({
    triggerId:  'region-trigger',
    panelId:    'region-panel',
    onSelect:   handleRegionChange,
    allLabel:   'All Regions'
  });

  // ── State multi-select ────────────────────────────────────────────────────
  buildMultiSelect({
    triggerId:  'state-trigger',
    panelId:    'state-panel',
    onSelect:   handleStateChange,
    allLabel:   'All States'
  });

  // Populate initial state options
  rebuildStateOptions();

  // ── From year ─────────────────────────────────────────────────────────────
  document.getElementById('from-year').addEventListener('change', e => {
    setState({ fromYear: e.target.value === 'all' ? null : e.target.value }, 'filterChanged');
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

// ── Multi-select builder ──────────────────────────────────────────────────────
function buildMultiSelect({ triggerId, panelId, onSelect, allLabel }) {
  const trigger = document.getElementById(triggerId);
  const panel   = document.getElementById(panelId);
  if (!trigger || !panel) return;

  trigger.addEventListener('click', e => {
    e.stopPropagation();
    document.querySelectorAll('.ms-panel').forEach(p => {
      if (p.id !== panelId) p.classList.add('hidden');
    });
    panel.classList.toggle('hidden');
  });

  document.addEventListener('click', e => {
    if (!panel.contains(e.target) && e.target !== trigger) {
      panel.classList.add('hidden');
    }
  });

  // Wire option clicks — works for both static HTML options (region)
  // and dynamically rebuilt options (state, via event delegation)
  panel.addEventListener('click', e => {
    const opt = e.target.closest('.ms-option');
    if (!opt) return;
    const cb = opt.querySelector('input[type=checkbox]');
    // Toggle unless click was directly on the checkbox (already toggled by browser)
    if (e.target !== cb) cb.checked = !cb.checked;
    onSelect(opt.dataset.value, cb.checked);
  });
}

// ── Region handling ───────────────────────────────────────────────────────────
function handleRegionChange(region, checked) {
  if (region === 'all') {
    _selectedRegions.clear();
    _selectedStates.clear();
  } else {
    if (checked) {
      _selectedRegions.add(region);
    } else {
      _selectedRegions.delete(region);
      // Remove states from this region from state selection
      const regionStates = _geoData.regions[region] || [];
      regionStates.forEach(s => _selectedStates.delete(s));
    }
  }
  syncRegionUI();
  rebuildStateOptions();
  pushGeoState();
}

function syncRegionUI() {
  const panel = document.getElementById('region-panel');
  if (!panel) return;
  panel.querySelectorAll('.ms-option').forEach(opt => {
    const val = opt.dataset.value;
    const cb  = opt.querySelector('input[type=checkbox]');
    if (val === 'all') {
      cb.checked = _selectedRegions.size === 0;
    } else {
      cb.checked = _selectedRegions.has(val);
    }
    opt.classList.toggle('selected', cb.checked);
  });
  updateTriggerLabel('region-trigger', _selectedRegions, 'All Regions', Array.from(_selectedRegions));
}

// ── State handling ────────────────────────────────────────────────────────────
function handleStateChange(abbr, checked) {
  if (abbr === 'all') {
    _selectedStates.clear();
  } else {
    if (checked) _selectedStates.add(abbr);
    else         _selectedStates.delete(abbr);
  }
  syncStateUI();
  pushGeoState();
}

function syncStateUI() {
  const panel = document.getElementById('state-panel');
  if (!panel) return;
  panel.querySelectorAll('.ms-option').forEach(opt => {
    const val = opt.dataset.value;
    const cb  = opt.querySelector('input[type=checkbox]');
    if (val === 'all') {
      cb.checked = _selectedStates.size === 0;
    } else {
      cb.checked = _selectedStates.has(val);
    }
    opt.classList.toggle('selected', cb.checked);
  });
  const stateNames = Array.from(_selectedStates).map(a => _geoData.stateNames[a] || a);
  updateTriggerLabel('state-trigger', _selectedStates, 'All States', stateNames);
}

function rebuildStateOptions() {
  const panel = document.getElementById('state-panel');
  if (!panel || !_geoData) return;

  const REGION_COLORS = { Northeast: '#58a6ff', Midwest: '#3fb950', South: '#f78166', West: '#e3b341' };

  // Which states to show: filtered by selected regions, or all
  const pool = _selectedRegions.size > 0
    ? Array.from(_selectedRegions).flatMap(r => _geoData.regions[r] || [])
    : Object.values(_geoData.regions).flat();

  pool.sort((a, b) => (_geoData.stateNames[a] || a).localeCompare(_geoData.stateNames[b] || b));

  let html = `<div class="ms-option ms-all" data-value="all">
    <input type="checkbox" ${_selectedStates.size === 0 ? 'checked' : ''}> All States
  </div>`;

  pool.forEach(abbr => {
    const region = _geoData.stateToRegion[abbr];
    const color  = REGION_COLORS[region] || '#888';
    html += `<div class="ms-option" data-value="${abbr}" style="--accent:${color}">
      <input type="checkbox" ${_selectedStates.has(abbr) ? 'checked' : ''}>
      <span class="ms-dot" style="background:${color}"></span>
      ${_geoData.stateNames[abbr] || abbr} <span class="ms-abbr">${abbr}</span>
    </div>`;
  });

  panel.innerHTML = html;

  panel.addEventListener('click', e => {
    const opt = e.target.closest('.ms-option');
    if (!opt) return;
    const cb  = opt.querySelector('input[type=checkbox]');
    cb.checked = !cb.checked;
    handleStateChange(opt.dataset.value, cb.checked);
  });
}

function pushGeoState() {
  // Resolve effective state set
  let states = null;

  if (_selectedStates.size > 0) {
    states = new Set(_selectedStates);
  } else if (_selectedRegions.size > 0) {
    states = new Set(Array.from(_selectedRegions).flatMap(r => _geoData.regions[r] || []));
  }

  const label = states === null
    ? 'All States'
    : states.size === 1
      ? [...states][0]
      : `${states.size} selected`;

  setState({ geo: { type: 'custom', label, states } }, 'filterChanged');
}

function updateTriggerLabel(triggerId, selectedSet, allLabel, names) {
  const trigger = document.getElementById(triggerId);
  if (!trigger) return;
  const label = trigger.querySelector('.ms-label');
  if (!label) return;
  if (selectedSet.size === 0) {
    label.textContent = allLabel;
  } else if (selectedSet.size === 1) {
    label.textContent = names[0];
  } else {
    label.textContent = `${selectedSet.size} selected`;
  }
}

// ── Populate period selectors ─────────────────────────────────────────────────
export function populatePeriodSelectors(periods) {
  const fmt = p => {
    const y = p.slice(0, 4), m = p.slice(4, 6);
    return new Date(+y, +m - 1).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  };

  const snapSel  = document.getElementById('snapshot-date');
  const startSel = document.getElementById('change-start-date');
  const endSel   = document.getElementById('change-end-date');
  const fromYear = document.getElementById('from-year');

  const reversed = [...periods].reverse();
  snapSel.innerHTML  = reversed.map(p => `<option value="${p}">${fmt(p)}</option>`).join('');
  startSel.innerHTML = periods.map(p => `<option value="${p}">${fmt(p)}</option>`).join('');
  endSel.innerHTML   = reversed.map(p => `<option value="${p}">${fmt(p)}</option>`).join('');

  snapSel.value  = periods[periods.length - 1];
  endSel.value   = periods[periods.length - 1];
  const defaultStartIdx = Math.max(0, periods.length - 25);
  startSel.value = periods[defaultStartIdx];

  const years = [...new Set(periods.map(p => p.slice(0, 4)))].sort();
  fromYear.innerHTML = `<option value="all">All Years</option>` +
    years.map(y => `<option value="${y}">${y}</option>`).join('');

  setState({
    snapshotPeriod:    periods[periods.length - 1],
    changeStartPeriod: periods[defaultStartIdx],
    changeEndPeriod:   periods[periods.length - 1]
  });
}

export function populatePMPMCategories(categories) {
  const catLabels = { total: 'Total Computable', federal: 'Federal Share', fedPct: 'Federal Share %', viii: 'Group VIII (ACA)', viiiNewElig: 'Group VIII Newly Eligible' };
  const sel = document.getElementById('pmpm-category');
  sel.innerHTML = categories.map(c =>
    `<option value="${c}">${catLabels[c] || c.charAt(0).toUpperCase() + c.slice(1)}</option>`
  ).join('');
}

// ── Repopulate only the map date selectors (snapshot + change) ────────────────
export function populateMapPeriodSelectors(periods, fmt) {
  if (!periods?.length) return;
  const snapSel  = document.getElementById('snapshot-date');
  const startSel = document.getElementById('change-start-date');
  const endSel   = document.getElementById('change-end-date');
  if (!snapSel) return;

  const reversed = [...periods].reverse();
  const toOpt = (p, arr) => arr.map(v => `<option value="${v}">${fmt(v)}</option>`).join('');

  snapSel.innerHTML  = toOpt(null, reversed);
  startSel.innerHTML = toOpt(null, periods);
  endSel.innerHTML   = toOpt(null, reversed);

  // Default: snapshot = most recent; change = earliest available → most recent
  snapSel.value  = periods[periods.length - 1];
  endSel.value   = periods[periods.length - 1];
  startSel.value = periods[0];

  setState({
    snapshotPeriod:    periods[periods.length - 1],
    changeStartPeriod: periods[0],
    changeEndPeriod:   periods[periods.length - 1]
  });
}

// ── Filter visibility ─────────────────────────────────────────────────────────
function updateFilterVisibility(metric) {
  const enrollGroup = document.getElementById('enrollment-type-group');
  const pmpmGroup   = document.getElementById('pmpm-category-group');
  const normToggle  = document.getElementById('trend-normalize-toggle');
  const snapCapBtn  = document.getElementById('snap-cap-btn');

  enrollGroup.style.display = metric === 'enrollment' ? '' : 'none';
  pmpmGroup.style.display   = metric === 'pmpm' ? '' : 'none';
  normToggle.style.display  = metric === 'enrollment' ? '' : 'none';
  if (snapCapBtn) snapCapBtn.style.display = metric === 'enrollment' ? '' : 'none';

  if (metric !== 'enrollment' && state.perCapita) {
    setState({ perCapita: false });
    document.querySelectorAll('.toggle-btn[data-value]').forEach(b => {
      b.classList.toggle('active', b.dataset.value === 'absolute');
    });
  }
}
