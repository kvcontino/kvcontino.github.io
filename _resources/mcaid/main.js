// js/main.js — app initialization

import { state, setState, setStatus, bus }    from './state.js';
import { fetchEnrollment, fetchManagedCare, fetchPMPM } from './api.js';
import { initFilters, populatePeriodSelectors, populatePMPMCategories } from './filters.js';
import { renderTrend }    from './trend.js';
import { loadTopoJSON, renderSnapshot, renderChange } from './geo.js';

let geoData, populations, topoJSON;

// ── Bootstrap ─────────────────────────────────────────────────────────────────
async function init() {
  // Load static reference data
  [geoData, populations, topoJSON] = await Promise.all([
    fetch('/_resources/mcaid/census-regions.json').then(r => r.json()),
    fetch('/_resources/mcaid/state-populations.json').then(r => r.json()),
    loadTopoJSON()
  ]);

  initFilters(geoData, populations);
  wireEvents();

  // Load enrollment data (required)
  await loadEnrollment();

  // Attempt managed care + PMPM in background, non-blocking
  loadManagedCare();
  loadPMPM();
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadEnrollment() {
  setStatus('enrollment', 'loading');
  setLoadingMessage('Connecting to data.medicaid.gov…', '');

  try {
    const { processed, cols } = await fetchEnrollment((msg, pct) => {
      setLoadingMessage(msg, `${pct}%`);
      setLoadingProgress(pct);
    });

    setState({
      enrollmentByState:  processed.byState,
      enrollmentByPeriod: processed.byPeriod,
      availablePeriods:   processed.sortedPeriods,
      latestPeriod:       processed.sortedPeriods[processed.sortedPeriods.length - 1],
      earliestPeriod:     processed.sortedPeriods[0],
      columnMap:          cols
    });

    populatePeriodSelectors(processed.sortedPeriods);
    updateDataCurrency(processed.sortedPeriods[processed.sortedPeriods.length - 1]);

    setStatus('enrollment', 'loaded');
    hideLoading();
    renderAll();

  } catch (err) {
    setStatus('enrollment', 'error', err.message);
    showError(`Enrollment data failed to load: ${err.message}`);
    hideLoading();
  }
}

async function loadManagedCare() {
  setStatus('managedCare', 'loading');
  setMetricAvailability('managed_care', 'loading');
  try {
    const data = await fetchManagedCare((msg) => {
      if (state.metric === 'managed_care') setLoadingMessage(msg, '');
    });
    setState({ managedCareData: data });
    setStatus('managedCare', 'loaded');
    setMetricAvailability('managed_care', 'loaded');
    if (state.metric === 'managed_care') renderAll();
  } catch (err) {
    setStatus('managedCare', 'error', err.message);
    setMetricAvailability('managed_care', 'error', err.message);
  }
}

async function loadPMPM() {
  setStatus('pmpm', 'loading');
  setMetricAvailability('pmpm', 'loading');
  try {
    const data = await fetchPMPM((msg) => {
      if (state.metric === 'pmpm') setLoadingMessage(msg, '');
    });
    setState({ pmpmData: data });
    populatePMPMCategories(data.categories);
    setStatus('pmpm', 'loaded');
    setMetricAvailability('pmpm', 'loaded');
    if (state.metric === 'pmpm') renderAll();
  } catch (err) {
    setStatus('pmpm', 'error', err.message);
    setMetricAvailability('pmpm', 'error', err.message);
  }
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderAll() {
  renderTrend(geoData, populations);
  renderSnapshot('map-snapshot', 'map-snapshot-legend', geoData, populations, topoJSON);
  renderChange('map-change',    'map-change-legend',    geoData, populations, topoJSON);
}

// ── Event wiring ──────────────────────────────────────────────────────────────
function wireEvents() {
  bus.on('metricChanged', () => {
    const { metric, status } = state;
    if (metric === 'managed_care' && status.managedCare === 'error') {
      showError('Managed care data unavailable: ' + state.errors.managedCare);
    } else if (metric === 'pmpm' && status.pmpm === 'error') {
      showError('Expenditure data unavailable: ' + state.errors.pmpm);
    } else {
      clearError();
    }
    renderAll();
  });

  bus.on('filterChanged', () => renderAll());

  document.getElementById('error-dismiss')?.addEventListener('click', clearError);

  // Resize — debounced redraw of choropleths
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      renderSnapshot('map-snapshot', 'map-snapshot-legend', geoData, populations, topoJSON);
      renderChange('map-change',    'map-change-legend',    geoData, populations, topoJSON);
    }, 200);
  });
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function setLoadingMessage(msg, sub) {
  const el = document.getElementById('loading-message');
  const sl = document.getElementById('loading-sub');
  if (el) el.textContent = msg;
  if (sl) sl.textContent = sub;
}

function setLoadingProgress(pct) {
  const bar = document.getElementById('loading-progress-bar');
  if (bar) bar.style.width = pct + '%';
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) {
    overlay.classList.add('fadeout');
    setTimeout(() => overlay.remove(), 600);
  }
}

function showError(msg) {
  const banner = document.getElementById('error-banner');
  const text   = document.getElementById('error-message');
  if (banner && text) {
    text.textContent = msg;
    banner.classList.remove('hidden');
  }
}

function clearError() {
  document.getElementById('error-banner')?.classList.add('hidden');
}

function updateDataCurrency(period) {
  const el = document.getElementById('data-currency');
  if (!el || !period) return;
  const y = period.slice(0, 4), m = period.slice(4, 6);
  const date = new Date(+y, +m - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  el.textContent = `Data through ${date}`;
}

function setMetricAvailability(metric, status, errorMsg) {
  const btn = document.querySelector(`.metric-tab[data-metric="${metric}"]`);
  if (!btn) return;
  btn.classList.remove('tab-loading', 'tab-error', 'tab-loaded');
  if (status === 'loading') btn.classList.add('tab-loading');
  if (status === 'error')   { btn.classList.add('tab-error'); btn.title = errorMsg || 'Unavailable'; }
  if (status === 'loaded')  btn.classList.add('tab-loaded');
}

// ── Start ─────────────────────────────────────────────────────────────────────
init().catch(err => {
  document.getElementById('loading-overlay')?.remove();
  showError(`Failed to initialize dashboard: ${err.message}`);
  console.error(err);
});
