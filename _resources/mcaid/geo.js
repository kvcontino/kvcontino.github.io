// js/geo.js — D3 choropleth factory

import { state } from './state.js';

const FIPS_TO_ABBR = {
  '01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE',
  '11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA',
  '20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN',
  '28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM',
  '36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI',
  '45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA',
  '54':'WV','55':'WI','56':'WY'
};

const ENROLLMENT_FIELD_TO_KEY = {
  'total_medicaid_and_chip_enrollment': 'total',
  'total_medicaid_enrollment':          'medicaid',
  'total_chip_enrollment':              'chip',
  'medicaid_and_chip_child_enrollment': 'children',
  'total_adult_medicaid_enrollment':    'adults'
};

let topoData = null;

export async function loadTopoJSON() {
  if (topoData) return topoData;
  const res = await fetch('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json');
  topoData = await res.json();
  return topoData;
}

// ── Snapshot choropleth ───────────────────────────────────────────────────────
export function renderSnapshot(containerId, legendId, geoData, populations, topoJSON) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  const { metric, enrollmentField, snapshotPeriod, perCapita, geo } = state;
  const field = ENROLLMENT_FIELD_TO_KEY[enrollmentField] || 'total';

  const stateValues = getSnapshotValues(metric, field, snapshotPeriod, perCapita, populations);
  if (!stateValues) return;

  const { valueMap, format, title, colorScheme } = stateValues;
  drawChoropleth(container, legendId, topoJSON, valueMap, format, colorScheme, geo, geoData, false, title);
}

// ── Change choropleth ─────────────────────────────────────────────────────────
export function renderChange(containerId, legendId, geoData, populations, topoJSON) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  const { metric, enrollmentField, changeStartPeriod, changeEndPeriod, geo } = state;
  const field = ENROLLMENT_FIELD_TO_KEY[enrollmentField] || 'total';

  const changeValues = getChangeValues(metric, field, changeStartPeriod, changeEndPeriod);
  if (!changeValues) return;

  const { valueMap, format, title } = changeValues;
  drawChoropleth(container, legendId, topoJSON, valueMap, format, 'diverging', geo, geoData, true, title);
}

// ── Value extraction ──────────────────────────────────────────────────────────
function getSnapshotValues(metric, field, period, perCapita, populations) {
  if (metric === 'enrollment') {
    const byPeriod = state.enrollmentByPeriod;
    if (!byPeriod || !period) return null;
    const periodData = byPeriod.get(period);
    if (!periodData) return null;

    const valueMap = new Map();
    periodData.forEach((vals, abbr) => {
      let v = vals[field];
      if (v === null || v === undefined) return;
      if (perCapita && populations[abbr]) v = v / populations[abbr] * 1000;
      valueMap.set(abbr, v);
    });
    const fmt = perCapita
      ? v => v.toFixed(1) + ' per 1K'
      : v => v >= 1_000_000 ? (v / 1_000_000).toFixed(2) + 'M' : v >= 1_000 ? (v / 1_000).toFixed(0) + 'K' : v.toFixed(0);
    return { valueMap, format: fmt, title: 'Enrollment', colorScheme: 'sequential' };
  }

  if (metric === 'managed_care') {
    const mc = state.managedCareData;
    if (!mc) return null;
    // Use latest year available
    const year = mc.sortedYears[mc.sortedYears.length - 1];
    const yearData = mc.byYear.get(year);
    if (!yearData) return null;
    const valueMap = new Map();
    yearData.forEach((rec, abbr) => { if (rec.pct !== null) valueMap.set(abbr, rec.pct); });
    return { valueMap, format: v => v.toFixed(1) + '%', title: `Managed Care % (${year})`, colorScheme: 'mc' };
  }

  if (metric === 'pmpm') {
    const pmpm = state.pmpmData;
    if (!pmpm) return null;
    const cat = state.pmpmCategory;
    const periodData = pmpm.byPeriod.get(period);
    if (!periodData) return null;
    const valueMap = new Map();
    periodData.forEach((vals, abbr) => { if (vals[cat] !== undefined) valueMap.set(abbr, vals[cat]); });
    return { valueMap, format: v => '$' + v.toFixed(2), title: 'PMPM Expenditure', colorScheme: 'pmpm' };
  }

  return null;
}

function getChangeValues(metric, field, startPeriod, endPeriod) {
  if (metric === 'enrollment') {
    const byPeriod = state.enrollmentByPeriod;
    if (!byPeriod || !startPeriod || !endPeriod) return null;
    const startData = byPeriod.get(startPeriod);
    const endData   = byPeriod.get(endPeriod);
    if (!startData || !endData) return null;

    const valueMap = new Map();
    endData.forEach((vals, abbr) => {
      const startVals = startData.get(abbr);
      if (!startVals) return;
      const startV = startVals[field], endV = vals[field];
      if (startV === null || endV === null || startV === 0) return;
      valueMap.set(abbr, ((endV - startV) / startV) * 100);
    });
    return { valueMap, format: v => (v >= 0 ? '+' : '') + v.toFixed(1) + '%', title: '% Change in Enrollment' };
  }

  if (metric === 'managed_care') {
    const mc = state.managedCareData;
    if (!mc) return null;
    // Use first and last year for change
    const years = mc.sortedYears;
    if (years.length < 2) return null;
    const [y0, y1] = [years[0], years[years.length - 1]];
    const valueMap = new Map();
    mc.byState.forEach((recs, abbr) => {
      const r0 = recs.find(r => r.year === y0), r1 = recs.find(r => r.year === y1);
      if (r0?.pct == null || r1?.pct == null) return;
      valueMap.set(abbr, r1.pct - r0.pct);   // percentage point change
    });
    return { valueMap, format: v => (v >= 0 ? '+' : '') + v.toFixed(1) + 'pp', title: `Managed Care % Change (${y0}→${y1})` };
  }

  return null;
}

// ── Core D3 drawing ───────────────────────────────────────────────────────────
function drawChoropleth(container, legendId, topoJSON, valueMap, format, scheme, geo, geoData, isDivergent, title) {
  const W = container.clientWidth  || 600;
  const H = Math.round(W * 0.62);  // ~975×610 ratio

  const projection = d3.geoAlbersUsa().scale(W * 1.25).translate([W / 2, H / 2]);
  const path = d3.geoPath().projection(projection);

  const svg = d3.select(container)
    .append('svg')
    .attr('viewBox', `0 0 ${W} ${H}`)
    .attr('width', '100%')
    .attr('height', '100%')
    .style('overflow', 'visible');

  const states = topojson.feature(topoJSON, topoJSON.objects.states).features;
  const values = [...valueMap.values()].filter(v => v !== null);

  // ── Color scale ───────────────────────────────────────────────────────────
  const colorScale = buildColorScale(scheme, values, isDivergent);

  // ── Draw state paths ──────────────────────────────────────────────────────
  const stateGroup = svg.append('g');
  const tooltip = document.getElementById('tooltip');

  stateGroup.selectAll('path')
    .data(states)
    .join('path')
    .attr('d', path)
    .attr('fill', d => {
      const abbr = FIPS_TO_ABBR[String(d.id).padStart(2, '0')];
      if (!abbr) return '#21262d';
      const v = valueMap.get(abbr);
      if (v === null || v === undefined) return '#2d333b';
      return colorScale(v);
    })
    .attr('stroke', d => {
      const abbr = FIPS_TO_ABBR[String(d.id).padStart(2, '0')];
      if (!geo.states || !abbr) return '#30363d';
      return geo.states.has(abbr) ? '#f0f6fc' : '#21262d';
    })
    .attr('stroke-width', d => {
      const abbr = FIPS_TO_ABBR[String(d.id).padStart(2, '0')];
      if (!geo.states || !abbr) return 0.5;
      return geo.states.has(abbr) ? 1.5 : 0.5;
    })
    .attr('class', 'state-path')
    .on('mouseover', function(event, d) {
      const abbr = FIPS_TO_ABBR[String(d.id).padStart(2, '0')];
      if (!abbr) return;
      d3.select(this).attr('stroke', '#f0f6fc').attr('stroke-width', 1.5).raise();
      showTooltip(event, abbr, valueMap, format, geoData, values, colorScale);
    })
    .on('mousemove', function(event) {
      moveTooltip(event);
    })
    .on('mouseout', function(event, d) {
      const abbr = FIPS_TO_ABBR[String(d.id).padStart(2, '0')];
      d3.select(this)
        .attr('stroke', (!geo.states || !abbr) ? '#30363d' : geo.states?.has(abbr) ? '#f0f6fc' : '#21262d')
        .attr('stroke-width', (!geo.states || !abbr) ? 0.5 : geo.states?.has(abbr) ? 1.5 : 0.5);
      if (tooltip) tooltip.classList.add('hidden');
    });

  // ── State mesh overlay ────────────────────────────────────────────────────
  svg.append('path')
    .datum(topojson.mesh(topoJSON, topoJSON.objects.states, (a, b) => a !== b))
    .attr('fill', 'none')
    .attr('stroke', '#21262d')
    .attr('stroke-width', 0.4)
    .attr('d', path)
    .style('pointer-events', 'none');

  // ── Legend ────────────────────────────────────────────────────────────────
  renderLegend(legendId, colorScale, values, format, isDivergent, scheme);
}

function buildColorScale(scheme, values, isDivergent) {
  if (!values.length) return () => '#2d333b';

  if (isDivergent) {
    const ext = Math.max(Math.abs(d3.min(values)), Math.abs(d3.max(values)));
    return d3.scaleDiverging(t => {
      if (t < 0.5) return d3.interpolateRgb('#ff7d00', '#21262d')(t * 2);
      return d3.interpolateRgb('#21262d', '#0083ff')((t - 0.5) * 2);
    }).domain([-ext, 0, ext]);
  }

  // Quantile scale for better visual discrimination (handles skewed distributions)
  const quantileVals = d3.quantile(values.slice().sort(d3.ascending), 0.95);
  const clampedMax   = quantileVals || d3.max(values);

  const interpolators = {
    sequential: t => d3.interpolateRgb('#0d2b3e', '#58a6ff')(t),
    mc:         t => d3.interpolateRgb('#1a1d4e', '#a371f7')(t),
    pmpm:       t => d3.interpolateRgb('#2e1a1a', '#f78166')(t)
  };
  const interp = interpolators[scheme] || interpolators.sequential;

  // Use quantile binning for 8 classes
  const quantiles = d3.scaleQuantile()
    .domain(values)
    .range(d3.range(8).map(i => interp(i / 7)));

  return quantiles;
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
function showTooltip(event, abbr, valueMap, format, geoData, allValues, colorScale) {
  const tooltip = document.getElementById('tooltip');
  if (!tooltip) return;

  const v = valueMap.get(abbr);
  const sortedVals = [...valueMap.entries()].filter(([,v]) => v !== null).sort(([,a],[,b]) => b - a);
  const rank = sortedVals.findIndex(([a]) => a === abbr) + 1;
  const stateName = geoData.stateNames[abbr] || abbr;
  const region    = geoData.stateToRegion[abbr] || '';
  const div       = geoData.stateToDiv[abbr] || '';

  let html = `<div class="tt-header">
    <span class="tt-abbr">${abbr}</span>
    <span class="tt-name">${stateName}</span>
  </div>`;

  if (v !== null && v !== undefined) {
    html += `<div class="tt-value">${format(v)}</div>`;
    html += `<div class="tt-meta">Rank ${rank} of ${sortedVals.length}</div>`;
  } else {
    html += `<div class="tt-value tt-nodata">No data</div>`;
  }
  html += `<div class="tt-geo">${region} · ${div}</div>`;

  tooltip.innerHTML = html;
  tooltip.classList.remove('hidden');
  moveTooltip(event);
}

function moveTooltip(event) {
  const tooltip = document.getElementById('tooltip');
  if (!tooltip) return;
  const x = event.clientX, y = event.clientY;
  const tw = tooltip.offsetWidth || 160, th = tooltip.offsetHeight || 80;
  const vw = window.innerWidth, vh = window.innerHeight;
  tooltip.style.left = Math.min(x + 14, vw - tw - 16) + 'px';
  tooltip.style.top  = Math.min(y - 14, vh - th - 16) + 'px';
}

// ── Legend ────────────────────────────────────────────────────────────────────
function renderLegend(legendId, colorScale, values, format, isDivergent, scheme) {
  const el = document.getElementById(legendId);
  if (!el) return;
  el.innerHTML = '';

  const W = 220, H = 12;
  const svg = d3.select(el).append('svg').attr('width', W + 60).attr('height', 36);

  const defs  = svg.append('defs');
  const gradId = legendId + '_grad';
  const grad  = defs.append('linearGradient').attr('id', gradId).attr('x1', '0%').attr('x2', '100%');

  const steps = 10;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    grad.append('stop')
      .attr('offset', t * 100 + '%')
      .attr('stop-color', isDivergent ? colorScale.interpolator()(t) : colorScale(d3.quantile(values.slice().sort(d3.ascending), t)));
  }

  svg.append('rect').attr('x', 28).attr('y', 0).attr('width', W).attr('height', H)
     .attr('fill', `url(#${gradId})`).attr('rx', 2);

  const vMin = d3.min(values), vMax = d3.max(values);
  svg.append('text').attr('x', 28).attr('y', H + 14).attr('fill', '#6e7681')
     .attr('font-size', 10).attr('font-family', "'IBM Plex Mono', monospace")
     .text(format(vMin));
  svg.append('text').attr('x', 28 + W).attr('y', H + 14).attr('fill', '#6e7681')
     .attr('font-size', 10).attr('font-family', "'IBM Plex Mono', monospace")
     .attr('text-anchor', 'end').text(format(vMax));

  if (isDivergent) {
    svg.append('text').attr('x', 28 + W / 2).attr('y', H + 14).attr('fill', '#6e7681')
       .attr('font-size', 10).attr('font-family', "'IBM Plex Mono', monospace")
       .attr('text-anchor', 'middle').text('0');
  }

  svg.append('text').attr('x', 26).attr('y', H + 14).attr('fill', '#6e7681')
     .attr('font-size', 9).attr('font-family', "'IBM Plex Mono', monospace")
     .attr('text-anchor', 'end').text(isDivergent ? '−' : 'Low');
}
