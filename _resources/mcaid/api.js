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
  if (cached && Array.isArray(cached)) return processManagedCare(cached);

  onProgress?.('Fetching managed care data…', 10);

  // Try pre-fetched static file first (committed by GitHub Actions)
  try {
    const res = await fetch('/_resources/mcaid/managed-care.json');
    if (res.ok) {
      const rows = await res.json();
      if (Array.isArray(rows) && rows.length > 0) {
        onProgress?.('Processing managed care data…', 80);
        const processed = processManagedCare(rows);
        cacheSet('managed_care', rows);
        onProgress?.('Ready', 100);
        return processed;
      }
    }
  } catch { /* fall through to live API */ }

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
    cacheSet('managed_care', rows);
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
  cacheSet('managed_care', rows);
  return processed;
}

function processManagedCare(rows) {
  const byYear  = new Map();
  const byState = new Map();

  const toNum = v => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(String(v).replace(/[,%]/g, '').trim());
    return isNaN(n) ? null : n;
  };

  for (const row of rows) {
    // Support both normalized keys (from convert_mc.py) and raw Socrata keys
    const abbr = row.state_abbreviation || row.state_abbr || row.abbreviation;
    const year = String(row.year || row.Year || row.fiscal_year || '').trim();
    if (!abbr || !year) continue;

    const total  = toNum(row.total_medicaid_enrollees ?? row['Total Medicaid Enrollees']);
    const inMC   = toNum(row.enrolled_any ?? row['Individuals Enrolled (Any)']);
    const inComp = toNum(row.enrolled_comprehensive ?? row['Individuals Enrolled (Comprehensive)']);
    const rawPct = toNum(row.pct_any ?? row['Percent of all Medicaid enrollees (Any)']);
    const rawPctComp = toNum(row.pct_comprehensive ?? row['Percent of all Medicaid enrollees (Comprehensive)']);

    // Percentages in CSV are whole numbers (e.g. "81.00%") already parsed to 81
    const pct     = rawPct ?? (total && inMC ? inMC / total * 100 : null);
    const pctComp = rawPctComp ?? (total && inComp ? inComp / total * 100 : null);

    const entry = { abbr, year, total, inMC, pct, inComp, pctComp };

    if (!byYear.has(year)) byYear.set(year, new Map());
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
// ── CMS-64 State name → abbreviation ─────────────────────────────────────────
const STATE_NAME_TO_ABBR = {
  'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA',
  'Colorado':'CO','Connecticut':'CT','Delaware':'DE','District of Columbia':'DC',
  'Florida':'FL','Georgia':'GA','Hawaii':'HI','Idaho':'ID','Illinois':'IL',
  'Indiana':'IN','Iowa':'IA','Kansas':'KS','Kentucky':'KY','Louisiana':'LA',
  'Maine':'ME','Maryland':'MD','Massachusetts':'MA','Michigan':'MI','Minnesota':'MN',
  'Mississippi':'MS','Missouri':'MO','Montana':'MT','Nebraska':'NE','Nevada':'NV',
  'New Hampshire':'NH','New Jersey':'NJ','New Mexico':'NM','New York':'NY',
  'North Carolina':'NC','North Dakota':'ND','Ohio':'OH','Oklahoma':'OK','Oregon':'OR',
  'Pennsylvania':'PA','Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD',
  'Tennessee':'TN','Texas':'TX','Utah':'UT','Vermont':'VT','Virginia':'VA',
  'Washington':'WA','West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY',
  'Puerto Rico':'PR','Guam':'GU','Virgin Islands':'VI',
  'Northern Mariana Islands':'MP','American Samoa':'AS'
};

export async function fetchPMPM(onProgress) {
  const cached = cacheGet('pmpm');
  if (cached && Array.isArray(cached)) return processPMPM(cached);

  // CMS-64 New Adult Group Expenditures — confirmed UUID
  const CMS64_UUID = '00505e90-f8ac-5921-b12f-5e23ba7ffcf3';
  onProgress?.('Fetching CMS-64 expenditure data…', 10);
  return await fetchPMPMFromUUID(CMS64_UUID, onProgress);
}

async function fetchPMPMFromUUID(uuid, onProgress) {
  let offset = 0, allRows = [];
  while (true) {
    const url = buildUrl(uuid, { limit: PAGE_LIMIT, offset });
    const r = await dkanGet(url);
    const batch = r.results || r.data || [];
    allRows.push(...batch);
    if (batch.length < PAGE_LIMIT) break;
    offset += PAGE_LIMIT;
    onProgress?.(`Loading expenditures… ${allRows.length.toLocaleString()} rows`, 50);
  }
  cacheSet('pmpm', allRows);
  return processPMPM(allRows);
}

function processPMPM(rows) {
  const byState  = new Map();
  const byPeriod = new Map();

  const parseNum = v => {
    if (!v || v === 'N/A' || v === '') return null;
    const n = Number(String(v).replace(/[,$]/g, ''));
    return isNaN(n) ? null : n;
  };

  // Quarter end date "2014-03-31" → "201403" for period key
  const periodKey = d => d ? d.slice(0, 7).replace('-', '') : null;
  const periodLabel = d => d ? d.slice(0, 7) : null;

  for (const row of rows) {
    const abbr = STATE_NAME_TO_ABBR[row.state?.trim()];
    if (!abbr) continue;
    const period = periodLabel(row.quarter_end_date);
    if (!period) continue;

    const total        = parseNum(row.total_computable_all_medical_assistance_expenditures);
    const federal      = parseNum(row.total_federal_share_all_medical_assistance_expenditures);
    const viii         = parseNum(row.total_computable_viii_group_expenditures);
    const viiiNewElig  = parseNum(row.total_computable_viii_group_newly_eligible_expenditures);
    const fedPct       = (total && federal) ? (federal / total * 100) : null;

    const entry = { total, federal, viii, viiiNewElig, fedPct };

    if (!byState.has(abbr)) byState.set(abbr, []);
    byState.get(abbr).push({ period, ...entry });
    if (!byPeriod.has(period)) byPeriod.set(period, new Map());
    byPeriod.get(period).set(abbr, entry);
  }

  byState.forEach(recs => recs.sort((a, b) => a.period.localeCompare(b.period)));
  const sortedPeriods = [...byPeriod.keys()].sort();

  return {
    byState, byPeriod, sortedPeriods,
    categories: ['total', 'federal', 'viii', 'viiiNewElig', 'fedPct']
  };
}
