// js/api.js — data fetching, caching, schema discovery

const DKAN_BASE   = 'https://data.medicaid.gov/api/1/datastore/query';
const ENROLLMENT_UUID = '6165f45b-ca93-5bb5-9d06-db29c692a360';
const MC_SOCRATA  = 'https://healthdata.gov/resource/m563-snjf.json';
const PAGE_LIMIT  = 1000;
const CACHE_TTL   = 60 * 60 * 1000; // 1h

// ── Session cache ─────────────────────────────────────────────────────────────
function cacheGet(key) {
  try {
    const raw = sessionStorage.getItem('mcd_' + key);
    if (!raw) return null;
    const { ts, data } = JSON.parse(raw);
    if (Date.now() - ts > CACHE_TTL) { sessionStorage.removeItem('mcd_' + key); return null; }
    return data;
  } catch { return null; }
}
function cacheSet(key, data) {
  try { sessionStorage.setItem('mcd_' + key, JSON.stringify({ ts: Date.now(), data })); }
  catch { /* quota exceeded — silent */ }
}

// ── Column normalization ──────────────────────────────────────────────────────
// DKAN converts CSV headers to snake_case; some special-char handling varies.
// We discover the actual keys from the first row and build a stable mapping.
const FIELD_PATTERNS = {
  state:       [/^state_abbre/i, /^abbr/i],
  stateName:   [/^state_name/i],
  period:      [/^reporting_period/i, /^period/i],
  isFinal:     [/^final_report/i, /^is_final/i],
  isPrelim:    [/^preliminary_or_updated/i],
  total:       [/^total_medicaid_and_chip_enroll/i, /^total_medicaid.*chip_enroll/i],
  medicaid:    [/^total_medicaid_enroll(?!ment_in)/i],
  chip:        [/^total_chip_enroll/i],
  children:    [/^medicaid.*chip.*child/i, /^child_enroll/i],
  adults:      [/^total_adult/i]
};

function discoverColumns(sampleRow) {
  const keys = Object.keys(sampleRow);
  const map = {};
  for (const [field, patterns] of Object.entries(FIELD_PATTERNS)) {
    const match = keys.find(k => patterns.some(p => p.test(k)));
    if (match) map[field] = match;
  }
  // Validate critical fields
  const required = ['state', 'period', 'total'];
  const missing = required.filter(f => !map[f]);
  if (missing.length) throw new Error(`Column discovery failed. Missing: ${missing.join(', ')}. Keys found: ${keys.slice(0, 8).join(', ')}`);
  return map;
}

// ── DKAN enrollment fetch (paginated) ─────────────────────────────────────────
export async function fetchEnrollment(onProgress) {
  const cached = cacheGet('enrollment');
  if (cached) { onProgress?.('Loaded from cache', 100); return cached; }

  onProgress?.('Fetching enrollment data…', 5);

  // Step 1: discover column names + get count
  const probeUrl = buildUrl(ENROLLMENT_UUID, { limit: 1, offset: 0 });
  const probe = await dkanGet(probeUrl);
  const count = probe.count || probe.total || 0;
  if (!probe.results?.length && !probe.data?.length)
    throw new Error('Enrollment API returned no rows. Check CORS or dataset availability.');

  const firstRow = (probe.results || probe.data)[0];
  const cols = discoverColumns(firstRow);

  onProgress?.(`Discovered schema. Fetching ${count.toLocaleString()} records…`, 10);

  // Step 2: paginate — only fetch Final/Updated rows
  const pages = Math.ceil(count / PAGE_LIMIT);
  const allRows = [];
  const batchSize = 4;

  for (let start = 0; start < pages; start += batchSize) {
    const batch = [];
    for (let p = start; p < Math.min(start + batchSize, pages); p++) {
      const url = buildUrl(ENROLLMENT_UUID, {
        limit: PAGE_LIMIT,
        offset: p * PAGE_LIMIT,
        // Filter to final/updated records only
        'conditions[0][property]': cols.isFinal || 'final_report',
        'conditions[0][value]': 'Y',
        'conditions[0][operator]': '='
      });
      batch.push(dkanGet(url));
    }
    const results = await Promise.all(batch);
    results.forEach(r => allRows.push(...(r.results || r.data || [])));
    const pct = Math.round(((start + batchSize) / pages) * 80) + 10;
    onProgress?.(`Loading… ${allRows.length.toLocaleString()} rows`, Math.min(pct, 90));
  }

  onProgress?.('Processing data…', 92);
  const processed = processEnrollment(allRows, cols);
  cacheSet('enrollment', { rows: allRows, cols, processed });
  onProgress?.('Ready', 100);
  return { rows: allRows, cols, processed };
}

function buildUrl(uuid, params) {
  const base = `${DKAN_BASE}/${uuid}/0`;
  const qs = Object.entries(params)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
  return `${base}?${qs}`;
}

async function dkanGet(url) {
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`DKAN API error ${res.status}: ${url.slice(0, 80)}`);
  return res.json();
}

// ── Data processing ───────────────────────────────────────────────────────────
function processEnrollment(rows, cols) {
  const byState  = new Map();   // abbr → [{period, values}]
  const byPeriod = new Map();   // period → Map<abbr, values>
  const periods  = new Set();
  const states   = new Set();

  const parseNum = v => {
    if (v === null || v === undefined || v === '' || v === 'N/A') return null;
    const n = Number(String(v).replace(/,/g, ''));
    return isNaN(n) ? null : n;
  };

  for (const row of rows) {
    const abbr   = row[cols.state];
    const period = row[cols.period];
    if (!abbr || !period) continue;

    const values = {
      total:    parseNum(row[cols.total]),
      medicaid: parseNum(row[cols.medicaid]),
      chip:     parseNum(row[cols.chip]),
      children: parseNum(row[cols.children]),
      adults:   parseNum(row[cols.adults])
    };

    // Skip rows where all values are null (footnote-only rows)
    if (Object.values(values).every(v => v === null)) continue;

    periods.add(period);
    states.add(abbr);

    if (!byState.has(abbr)) byState.set(abbr, []);
    byState.get(abbr).push({ period, ...values });

    if (!byPeriod.has(period)) byPeriod.set(period, new Map());
    byPeriod.get(period).set(abbr, values);
  }

  // Sort each state's records chronologically
  byState.forEach(recs => recs.sort((a, b) => a.period.localeCompare(b.period)));

  const sortedPeriods = [...periods].sort();

  return { byState, byPeriod, sortedPeriods, states: [...states].sort() };
}

// ── Managed care fetch ────────────────────────────────────────────────────────
export async function fetchManagedCare(onProgress) {
  const cached = cacheGet('managed_care');
  if (cached) return cached;

  onProgress?.('Fetching managed care data…', 10);

  // Try healthdata.gov Socrata endpoint (annual data)
    try {
    const url = `${MC_SOCRATA}?$limit=5000&$order=year DESC`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10_000);
    const res = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: controller.signal
    });
    clearTimeout(timeout);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const rows = await res.json();
    if (!Array.isArray(rows) || rows.length === 0) throw new Error('Empty response');
    onProgress?.('Processing managed care data…', 80);
    const processed = processManagedCare(rows);
    cacheSet('managed_care', processed);
    onProgress?.('Ready', 100);
    return processed;
  } catch (err) {
    console.warn('Managed care fetch failed (healthdata.gov):', err.message);
    return await tryManagedCareCSVs(onProgress);
  }
}

async function tryManagedCareCSVs(onProgress) {
  const years = [2024, 2023, 2022, 2021, 2020, 2019];
  const allRows = [];

  for (const year of years) {
    const url = `https://download.medicaid.gov/data/share-of-medicaid-enrollees-in-managed-care.${year}-table5.csv`;
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const text = await res.text();
      const parsed = parseCSV(text, year);
      allRows.push(...parsed);
      onProgress?.(`Loaded ${year} managed care data`, 50);
    } catch { continue; }
  }

  if (allRows.length === 0) {
    throw new Error('Managed care data unavailable. The source (download.medicaid.gov) does not support CORS from browsers. Consider using a GitHub Action to pre-fetch this data as static JSON.');
  }

  const processed = processManagedCare(allRows);
  cacheSet('managed_care', processed);
  return processed;
}

function processManagedCare(rows) {
  // Normalize regardless of Socrata vs CSV source
  const byYear  = new Map();
  const byState = new Map();

  const findField = (row, patterns) => {
    const keys = Object.keys(row);
    for (const p of patterns) {
      const k = keys.find(k => p.test(k));
      if (k !== undefined) return row[k];
    }
    return null;
  };
  const parseNum = v => {
    if (!v || v === 'n/a' || v === 'N/A' || v === 'NA') return null;
    const n = Number(String(v).replace(/[,%]/g, ''));
    return isNaN(n) ? null : n;
  };

  for (const row of rows) {
    const abbr  = findField(row, [/^state_abbreviation/i, /^abbreviation/i, /^state_abbr/i]);
    const year  = String(findField(row, [/^year/i, /^fy/i, /^fiscal_year/i]) || '');
    const total = parseNum(findField(row, [/total_medicaid_enroll/i, /^total_enrollees/i]));
    const inMC  = parseNum(findField(row, [/total.*managed_care/i, /any.*managed/i, /in_any/i]));
    const pct   = parseNum(findField(row, [/percent.*managed/i, /pct.*managed/i, /share.*managed/i, /%.*managed/i]));
    const inComp = parseNum(findField(row, [/comprehensive.*managed/i, /comprehensive_mc/i]));
    const pctComp = parseNum(findField(row, [/percent.*comprehensive/i, /pct.*comprehensive/i]));

    if (!abbr || !year) continue;

    const entry = { abbr, year, total, inMC, pct: pct ?? (total && inMC ? inMC / total * 100 : null), inComp, pctComp };

    if (!byYear.has(year))  byYear.set(year, new Map());
    byYear.get(year).set(abbr, entry);

    if (!byState.has(abbr)) byState.set(abbr, []);
    byState.get(abbr).push(entry);
  }

  byState.forEach(recs => recs.sort((a, b) => a.year.localeCompare(b.year)));
  const sortedYears = [...byYear.keys()].sort();

  return { byYear, byState, sortedYears };
}

function parseCSV(text, year) {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map(h => h.replace(/"/g, '').trim().toLowerCase().replace(/\s+/g, '_'));
  return lines.slice(1).map(line => {
    const vals = line.split(',').map(v => v.replace(/"/g, '').trim());
    const obj = { year };
    headers.forEach((h, i) => { obj[h] = vals[i]; });
    return obj;
  });
}

// ── PMPM fetch (catalog discovery attempt) ────────────────────────────────────
export async function fetchPMPM(_onProgress) {
  // Known candidate DKAN UUIDs for MBES expenditure data
  // These will be verified at runtime; if none respond correctly, we degrade gracefully.
  const candidates = [
    '6c114b2c-cb59-5e07-9e42-92f71ecc22a5',  // MBES T-19 (expenditures by service)
    'dea65a5f-8ee3-5b8d-b1df-5fd33e7f8cfd',  // Medicaid expenditure data
  ];

  for (const uuid of candidates) {
    try {
      const url = buildUrl(uuid, { limit: 1, offset: 0 });
      const probe = await dkanGet(url);
      const row = (probe.results || probe.data || [])[0];
      if (!row) continue;
      // Verify it looks like expenditure data
      const keys = Object.keys(row);
      const hasExpenditure = keys.some(k => /expend|pmpm|per_member/i.test(k));
      if (!hasExpenditure) continue;
      // Full fetch
      return await fetchPMPMFromUUID(uuid);
    } catch { continue; }
  }

  throw new Error('PMPM/expenditure data not found via auto-discovery. The CMS MBES dataset may require a different access path. Consider pre-fetching via GitHub Actions.');
}

async function fetchPMPMFromUUID(uuid) {
  let offset = 0, allRows = [];
  while (true) {
    const url = buildUrl(uuid, { limit: PAGE_LIMIT, offset });
    const r = await dkanGet(url);
    const batch = r.results || r.data || [];
    allRows.push(...batch);
    if (batch.length < PAGE_LIMIT) break;
    offset += PAGE_LIMIT;
  }
  const processed = processPMPM(allRows);
  cacheSet('pmpm', processed);
  return processed;
}

function processPMPM(rows) {
  // Generic processor; adapts to whatever schema is discovered
  const byState  = new Map();
  const byPeriod = new Map();
  const categories = new Set(['total']);

  const parseNum = v => { const n = Number(String(v || '').replace(/[,$]/g, '')); return isNaN(n) ? null : n; };

  for (const row of rows) {
    const keys   = Object.keys(row);
    const abbr   = row[keys.find(k => /state_abbr/i.test(k))] || row[keys.find(k => /^state$/i.test(k))];
    const period = row[keys.find(k => /period|year|quarter/i.test(k))];
    if (!abbr || !period) continue;

    const pmpm = {};
    keys.filter(k => /expend|pmpm|per_member/i.test(k)).forEach(k => {
      const cat = k.replace(/pmpm_|expenditure_|per_member_/gi, '').replace(/_/g, ' ').trim() || 'total';
      categories.add(cat);
      pmpm[cat] = parseNum(row[k]);
    });

    if (!byState.has(abbr))  byState.set(abbr, []);
    byState.get(abbr).push({ period, ...pmpm });
    if (!byPeriod.has(period)) byPeriod.set(period, new Map());
    byPeriod.get(period).set(abbr, pmpm);
  }

  byState.forEach(recs => recs.sort((a, b) => a.period.localeCompare(b.period)));
  const sortedPeriods = [...byPeriod.keys()].sort();

  return { byState, byPeriod, sortedPeriods, categories: [...categories] };
}
