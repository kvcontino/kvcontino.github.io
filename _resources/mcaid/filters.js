// js/filters.js — filter UI components

import { state, setState, bus } from './state.js';

let _geoData = null;

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

  // ── Region select ─────────────────────────────────────────────────────────
  const regionSel = document.getElementById('region-select');
  regionSel.addEventListener('change', () => {
    const region = regionSel.value;
    populateStateSelect(region);
    const states = region === 'all' ? null : new Set(geoData.regions[region]);
    setState({
      geo: { type: region === 'all' ? 'all' : 'region', label: region === 'all' ? 'All States' : region, states }
    }, 'filterChanged');
  });

  // ── State select ──────────────────────────────────────────────────────────
  const stateSel = document.getElementById('state-select');
  stateSel.addEventListener('change', () => {
    const abbr = stateSel.value;
    if (abbr === 'all') {
      const region = regionSel.value;
      const states = region === 'all' ? null : new Set(geoData.regions[region]);
      setState({
        geo: { type: region === 'all' ? 'all' : 'region', label: region === 'all' ? 'All States' : region, states }
      }, 'filterChanged');
    } else {
      setState({
        geo: { type: 'state', label: `${abbr} — ${geoData.stateNames[abbr] || abbr}`, states: new Set([abbr]) }
      }, 'filterChanged');
    }
  });

  // ── From year ─────────────────────────────────────────────────────────────
  const fromYear = document.getElementById('from-year');
  fromYear.addEventListener('change', () => {
    setState({ fromYear: fromYear.value === 'all' ? null : fromYear.value }, 'filterChanged');
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

  // Build initial state dropdown
  populateStateSelect('all');
}

// ── Populate state dropdown based on selected region ──────────────────────────
function populateStateSelect(region) {
  const stateSel = document.getElementById('state-select');
  const states = region === 'all'
    ? Object.values(_geoData.regions).flat().sort((a, b) =>
        (_geoData.stateNames[a] || a).localeCompare(_geoData.stateNames[b] || b))
    : (_geoData.regions[region] || []).slice().sort((a, b) =>
        (_geoData.stateNames[a] || a).localeCompare(_geoData.stateNames[b] || b));

  stateSel.innerHTML = `<option value="all">All States</option>` +
    states.map(abbr =>
      `<option value="${abbr}">${_geoData.stateNames[abbr] || abbr} (${abbr})</option>`
    ).join('');
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

  snapSel.value = periods[periods.length - 1];
  endSel.value  = periods[periods.length - 1];
  const defaultStartIdx = Math.max(0, periods.length - 25);
  startSel.value = periods[defaultStartIdx];

  // From-year selector — unique years from periods
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
  const sel = document.getElementById('pmpm-category');
  sel.innerHTML = categories.map(c =>
    `<option value="${c}">${c.charAt(0).toUpperCase() + c.slice(1)}</option>`
  ).join('');
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

  if (snapCapBtn) {
    snapCapBtn.style.display = metric === 'enrollment' ? '' : 'none';
  }

  // Reset per-capita directly without firing a button click
  if (metric !== 'enrollment' && state.perCapita) {
    setState({ perCapita: false });
    document.querySelectorAll('.toggle-btn[data-value]').forEach(b => {
      b.classList.toggle('active', b.dataset.value === 'absolute');
    });
  }
}
