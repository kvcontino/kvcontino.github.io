// js/main.js — app initialization

import { state, setState, setStatus, bus }    from './state.js';
import { fetchEnrollment, fetchManagedCare, fetchPMPM } from './api.js';
import { initFilters, populatePeriodSelectors, populateMapPeriodSelectors, populatePMPMCategories } from './filters.js';
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
    updatePanelDescriptions('enrollment');
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
        if (state.metric === 'managed_care') {
          refreshPeriodSelectorsForMetric('managed_care');
          renderAll();
        }
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
        if (state.metric === 'pmpm') {
          refreshPeriodSelectorsForMetric('pmpm');
          renderAll();
        }
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
    refreshPeriodSelectorsForMetric(metric);
    updatePanelDescriptions(metric);
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

// ── Period selectors per metric ──────────────────────────────────────────────
function refreshPeriodSelectorsForMetric(metric) {
  if (metric === 'enrollment') {
    if (state.availablePeriods?.length) {
      populateMapPeriodSelectors(state.availablePeriods, p => {
        const y = p.slice(0, 4), m = p.slice(4, 6);
        return new Date(+y, +m - 1).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
      });
    }
  } else if (metric === 'managed_care' && state.managedCareData?.sortedYears?.length) {
    populateMapPeriodSelectors(state.managedCareData.sortedYears, y => y);
  } else if (metric === 'pmpm' && state.pmpmData?.sortedPeriods?.length) {
    populateMapPeriodSelectors(state.pmpmData.sortedPeriods, p => {
      if (p.length === 6) {
        const y = p.slice(0, 4), m = p.slice(4, 6);
        return new Date(+y, +m - 1).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
      }
      return p;
    });
  }
}

// ── Panel descriptions ────────────────────────────────────────────────────────
const PANEL_DESCRIPTIONS = {
  enrollment: {
    trend: `Monthly state Medicaid &amp; CHIP enrollment. Source: <a href="https://data.medicaid.gov" target="_blank" rel="noopener">data.medicaid.gov</a> — CMS T-MSIS enrollment file (DKAN API, UUID 6165f45b). Final reports only. Covers all 50 states + DC. Data typically lags 3–6 months.`,
    snapshot: `Point-in-time enrollment count by state. Select a reporting month above. Per-capita toggle divides by 2023 Census population estimates.`,
    change: `Percent change in enrollment between two selected months. Diverging scale: orange = decline, blue = increase.`
  },
  managed_care: {
    trend: `Annual share of Medicaid enrollees enrolled in managed care organizations. Source: <a href="https://download.medicaid.gov" target="_blank" rel="noopener">download.medicaid.gov</a> — CMS Table 5 (2024). Managed care includes comprehensive managed care and primary care case management.`,
    snapshot: `Share of Medicaid enrollees in any managed care arrangement by state, for the most recent available year.`,
    change: `Percentage point change in managed care penetration between first and last available year.`
  },
  pmpm: {
    trend: `Quarterly total computable Medicaid expenditures by region. Source: <a href="https://data.medicaid.gov" target="_blank" rel="noopener">data.medicaid.gov</a> — CMS-64 Quarterly Expenditure Report (UUID 00505e90). Total computable = combined federal and state share. Federal share % reflects FMAP. Group VIII = ACA Medicaid expansion population (states with <code>N/A</code> did not expand).`,
    snapshot: `Quarterly expenditures by state for the selected period. Group VIII data only available for expansion states.`,
    change: `Change in expenditures between two selected quarters.`
  }
};

function updatePanelDescriptions(metric) {
  const desc = PANEL_DESCRIPTIONS[metric];
  if (!desc) return;
  const trend    = document.getElementById('trend-desc');
  const snapshot = document.getElementById('snapshot-desc');
  const change   = document.getElementById('change-desc');
  if (trend)    trend.innerHTML    = desc.trend;
  if (snapshot) snapshot.innerHTML = desc.snapshot;
  if (change)   change.innerHTML   = desc.change;
}

// ── Start ─────────────────────────────────────────────────────────────────────
init().catch(err => {
  document.getElementById('loading-overlay')?.remove();
  showError(`Failed to initialize dashboard: ${err.message}`);
  console.error(err);
});
