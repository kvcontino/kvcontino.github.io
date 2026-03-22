// js/trend.js — Chart.js enrollment / managed-care / pmpm trend chart

import { state } from './state.js';

let chartInstance = null;

const REGION_COLORS = {
  Northeast: '#58a6ff',
  Midwest:   '#3fb950',
  South:     '#f78166',
  West:      '#e3b341',
  National:  '#c9d1d9'
};

const FIELD_LABELS = {
  total:    'Total Medicaid & CHIP',
  medicaid: 'Medicaid Only',
  chip:     'CHIP Only',
  children: 'Children',
  adults:   'Adults'
};

const ENROLLMENT_FIELD_TO_KEY = {
  'total_medicaid_and_chip_enrollment': 'total',
  'total_medicaid_enrollment':          'medicaid',
  'total_chip_enrollment':              'chip',
  'medicaid_and_chip_child_enrollment': 'children',
  'total_adult_medicaid_enrollment':    'adults'
};

export function renderTrend(geoData, populations) {
  const { metric, enrollmentField, geo, perCapita } = state;
  const canvas = document.getElementById('trend-chart');
  if (!canvas) return;

  const { labels, datasets, title, yAxisLabel } = buildChartData(geoData, populations, metric, enrollmentField, geo, perCapita);

  if (chartInstance) chartInstance.destroy();

  chartInstance = new Chart(canvas, {
    type: 'line',
    data: { labels, datasets },
    options: chartOptions(title, yAxisLabel, metric, perCapita)
  });

  document.getElementById('trend-title').textContent = title;
}

function buildChartData(geoData, populations, metric, enrollmentField, geo, perCapita) {
  if (metric === 'enrollment') return buildEnrollmentSeries(geoData, populations, enrollmentField, geo, perCapita);
  if (metric === 'managed_care') return buildManagedCareSeries(geoData, geo);
  return buildPMPMSeries(geoData, geo);
}

// ── Enrollment series ────────────────────────────────────────────────────────
function buildEnrollmentSeries(geoData, populations, enrollmentField, geo, perCapita) {
  const { byState, sortedPeriods } = state.enrollmentByState ? { byState: state.enrollmentByState, sortedPeriods: state.availablePeriods } : { byState: null, sortedPeriods: [] };
  if (!byState) return { labels: [], datasets: [], title: 'Enrollment Trend', yAxisLabel: '' };

  const field = ENROLLMENT_FIELD_TO_KEY[enrollmentField] || 'total';
  const fieldLabel = FIELD_LABELS[field] || field;

  const labels = sortedPeriods.map(formatPeriod);
  let datasets = [];

  if (!geo.states) {
    // All states: show one line per Census region + national total
    datasets = buildRegionLines(byState, sortedPeriods, field, perCapita, geoData, populations);
  } else if (geo.type === 'state' && geo.states.size === 1) {
    const abbr = [...geo.states][0];
    const series = getStateSeries(byState, sortedPeriods, abbr, field);
    const pop = populations[abbr] || 1;
    datasets = [{
      label: geoData.stateNames[abbr] || abbr,
      data:  perCapita ? series.map(v => v !== null ? (v / pop * 1000) : null) : series,
      borderColor: '#58a6ff',
      backgroundColor: 'rgba(88,166,255,0.08)',
      borderWidth: 2.5,
      pointRadius: 0,
      pointHoverRadius: 5,
      tension: 0.3,
      fill: true
    }];
  } else {
    // Region or division: one line per state
    const stateList = [...geo.states];
    stateList.sort((a, b) => (geoData.stateNames[a] || a).localeCompare(geoData.stateNames[b] || b));
    datasets = stateList.slice(0, 15).map((abbr, i) => {
      const series = getStateSeries(byState, sortedPeriods, abbr, field);
      const pop = populations[abbr] || 1;
      const region = geoData.stateToRegion[abbr];
      const base = REGION_COLORS[region] || '#888';
      return {
        label: abbr,
        data:  perCapita ? series.map(v => v !== null ? (v / pop * 1000) : null) : series,
        borderColor: colorVariant(base, i, stateList.length),
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.3
      };
    });
    if (stateList.length > 15) {
      datasets.push({ label: `…+${stateList.length - 15} more (select fewer states)`, data: [], hidden: true });
    }
  }

  const unit = perCapita ? 'per 1,000 residents' : 'enrollees';
  return {
    labels,
    datasets,
    title: `${fieldLabel} Enrollment Trend`,
    yAxisLabel: perCapita ? `Enrollment (per 1K population)` : 'Total Enrollment'
  };
}

function buildRegionLines(byState, sortedPeriods, field, perCapita, geoData, populations) {
  const regionTotals = {};
  const regionPops = {};
  for (const [region, states] of Object.entries(geoData.regions)) {
    regionTotals[region] = {};
    regionPops[region] = states.reduce((sum, abbr) => sum + (populations[abbr] || 0), 0);
  }
  let nationalTotal = {};
  const nationalPop = Object.values(populations).reduce((a, b) => a + b, 0);

  byState.forEach((records, abbr) => {
    const region = geoData.stateToRegion[abbr];
    if (!region) return;
    records.forEach(rec => {
      const v = rec[field];
      if (v === null) return;
      regionTotals[region][rec.period] = (regionTotals[region][rec.period] || 0) + v;
      nationalTotal[rec.period] = (nationalTotal[rec.period] || 0) + v;
    });
  });

  const datasets = Object.entries(geoData.regions).map(([region]) => {
    const pop = regionPops[region] || 1;
    const data = sortedPeriods.map(p => {
      const v = regionTotals[region][p] ?? null;
      return v === null ? null : (perCapita ? v / pop * 1000 : v);
    });
    return {
      label: region,
      data,
      borderColor: REGION_COLORS[region],
      backgroundColor: `${REGION_COLORS[region]}18`,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 4,
      tension: 0.3,
      fill: false
    };
  });

  // National total (dashed)
  datasets.push({
    label: 'National Total',
    data: sortedPeriods.map(p => {
      const v = nationalTotal[p] ?? null;
      return v === null ? null : (perCapita ? v / nationalPop * 1000 : v);
    }),
    borderColor: REGION_COLORS.National,
    backgroundColor: 'transparent',
    borderWidth: 2,
    borderDash: [5, 3],
    pointRadius: 0,
    pointHoverRadius: 4,
    tension: 0.3
  });

  return datasets;
}

// ── Managed care series ───────────────────────────────────────────────────────
function buildManagedCareSeries(geoData, geo) {
  const mcData = state.managedCareData;
  if (!mcData) return { labels: [], datasets: [], title: 'Managed Care Trend', yAxisLabel: '' };

  const { byState, sortedYears } = mcData;
  const labels = sortedYears;
  let datasets = [];

  if (!geo.states) {
    // Regional averages
    datasets = Object.entries(geoData.regions).map(([region, states]) => {
      const data = sortedYears.map(yr => {
        const vals = states.map(abbr => {
          const recs = byState.get(abbr);
          const rec = recs?.find(r => r.year === yr);
          return rec?.pct;
        }).filter(v => v !== null && v !== undefined);
        return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
      });
      return {
        label: region,
        data,
        borderColor: REGION_COLORS[region],
        borderWidth: 2,
        pointRadius: 4,
        tension: 0.3
      };
    });
  } else {
    const stateList = [...geo.states];
    datasets = stateList.slice(0, 15).map((abbr, i) => {
      const recs = byState.get(abbr) || [];
      const data = sortedYears.map(yr => recs.find(r => r.year === yr)?.pct ?? null);
      return {
        label: abbr,
        data,
        borderColor: colorVariant('#a371f7', i, stateList.length),
        borderWidth: 1.5,
        pointRadius: 3,
        tension: 0.3
      };
    });
  }

  return { labels, datasets, title: 'Managed Care Penetration', yAxisLabel: '% of Enrollees in Managed Care' };
}

// ── PMPM series ───────────────────────────────────────────────────────────────
function buildPMPMSeries(geoData, geo) {
  const pmpmData = state.pmpmData;
  if (!pmpmData) return { labels: [], datasets: [], title: 'PMPM Expenditures', yAxisLabel: '' };

  const { byState, sortedPeriods } = pmpmData;
  const category = state.pmpmCategory;
  const labels = sortedPeriods.map(formatPeriod);
  const stateList = geo.states ? [...geo.states] : Object.keys(geoData.regions).flatMap(r => geoData.regions[r]).slice(0, 10);

  const datasets = stateList.slice(0, 15).map((abbr, i) => {
    const recs = byState.get(abbr) || [];
    const data = sortedPeriods.map(p => recs.find(r => r.period === p)?.[category] ?? null);
    return {
      label: abbr,
      data,
      borderColor: colorVariant('#f78166', i, stateList.length),
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3
    };
  });

  return { labels, datasets, title: `PMPM Expenditures — ${category}`, yAxisLabel: 'Per Member Per Month ($)' };
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function getStateSeries(byState, periods, abbr, field) {
  const recs = byState.get(abbr) || [];
  const map = new Map(recs.map(r => [r.period, r[field]]));
  return periods.map(p => map.get(p) ?? null);
}

function formatPeriod(p) {
  if (!p || p.length !== 6) return p;
  const d = new Date(+p.slice(0, 4), +p.slice(4, 6) - 1);
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

function colorVariant(baseHex, index, total) {
  // Rotate hue slightly for each state in a group
  const offset = total > 1 ? (index / total) * 60 - 30 : 0;
  return shiftHue(baseHex, offset);
}

function shiftHue(hex, deg) {
  // Simple hue shift — convert to HSL, adjust, return hex
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  let h = 0;
  if (d !== 0) {
    if (max === r) h = ((g - b) / d % 6) * 60;
    else if (max === g) h = (b - r) / d * 60 + 120;
    else h = (r - g) / d * 60 + 240;
  }
  h = ((h + deg) % 360 + 360) % 360;
  const s = max === 0 ? 0 : d / max;
  const v = max;
  const hi = Math.floor(h / 60) % 6, f = h / 60 - Math.floor(h / 60);
  const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  const rgb = [[v,t,p],[q,v,p],[p,v,t],[p,q,v],[t,p,v],[v,p,q]][hi];
  return '#' + rgb.map(c => Math.round(c * 255).toString(16).padStart(2, '0')).join('');
}

// ── Chart.js options ──────────────────────────────────────────────────────────
function chartOptions(title, yLabel, metric, perCapita) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        display: true,
        position: 'bottom',
        labels: {
          color: '#8b949e',
          font: { family: "'IBM Plex Mono', monospace", size: 11 },
          boxWidth: 12,
          padding: 16
        }
      },
      tooltip: {
        backgroundColor: '#1c2128',
        borderColor: '#30363d',
        borderWidth: 1,
        titleColor: '#c9d1d9',
        bodyColor: '#8b949e',
        titleFont: { family: "'IBM Plex Sans', sans-serif", size: 12, weight: '500' },
        bodyFont:  { family: "'IBM Plex Mono', monospace", size: 11 },
        padding: 10,
        callbacks: {
          label: ctx => {
            const v = ctx.parsed.y;
            if (v === null || v === undefined) return null;
            let formatted;
            if (metric === 'managed_care' || (metric === 'enrollment' && perCapita)) {
              formatted = v.toFixed(1) + (metric === 'managed_care' ? '%' : '');
            } else if (metric === 'pmpm') {
              formatted = '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            } else {
              formatted = formatLargeNum(v);
            }
            return `  ${ctx.dataset.label}: ${formatted}`;
          }
        }
      }
    },
    scales: {
      x: {
        ticks: {
          color: '#6e7681',
          font: { family: "'IBM Plex Mono', monospace", size: 10 },
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 18
        },
        grid: { color: '#21262d' }
      },
      y: {
        title: { display: true, text: yLabel, color: '#6e7681', font: { family: "'IBM Plex Sans'", size: 11 } },
        ticks: {
          color: '#6e7681',
          font: { family: "'IBM Plex Mono', monospace", size: 10 },
          callback: v => {
            if (metric === 'managed_care') return v.toFixed(0) + '%';
            if (metric === 'pmpm') return '$' + formatLargeNum(v);
            if (perCapita) return v.toFixed(1);
            return formatLargeNum(v);
          }
        },
        grid: { color: '#21262d' }
      }
    }
  };
}

function formatLargeNum(v) {
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
  if (Math.abs(v) >= 1_000)     return (v / 1_000).toFixed(0) + 'K';
  return v.toFixed(0);
}
