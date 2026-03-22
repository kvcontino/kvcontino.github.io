// js/state.js — shared application state + lightweight event bus

const _listeners = {};

export const bus = {
  on(event, fn)  { (_listeners[event] = _listeners[event] || []).push(fn); },
  off(event, fn) { _listeners[event] = (_listeners[event] || []).filter(f => f !== fn); },
  emit(event, data) { (_listeners[event] || []).forEach(fn => fn(data)); }
};

export const state = {
  // Active metric tab
  metric: 'enrollment',           // 'enrollment' | 'managed_care' | 'pmpm'

  // Enrollment sub-filters
  enrollmentField: 'total_medicaid_and_chip_enrollment',
  pmpmCategory:    'total',

  // Geo selection
  geo: { type: 'all', label: 'All States', states: null },
  // type: 'all' | 'region' | 'division' | 'state'
  // states: null (all) or Set of state abbrs

  // Per-capita toggle
  perCapita: false,

  // Choropleth controls
  snapshotPeriod:   null,   // YYYYMM string
  changeStartPeriod: null,
  changeEndPeriod:   null,

  // Processed data
  enrollmentByState:  null,   // Map<abbr, [{period, values}]>
  enrollmentByPeriod: null,   // Map<period, Map<abbr, values>>
  managedCareData:    null,   // Map<year, Map<abbr, {total, inMC, pct, inComprehensive, pctComp}>>
  pmpmData:           null,

  // Meta
  availablePeriods: [],         // sorted YYYYMM strings
  latestPeriod:     null,
  earliestPeriod:   null,
  columnMap:        null,       // discovered column name mapping

  // Status
  status: {
    enrollment:   'pending',   // 'pending'|'loading'|'loaded'|'error'
    managedCare:  'pending',
    pmpm:         'pending'
  },
  errors: {}
};

export function setState(patch, eventName = 'stateChanged') {
  Object.assign(state, patch);
  bus.emit(eventName, state);
}

export function setStatus(key, value, error = null) {
  state.status[key] = value;
  if (error) state.errors[key] = error;
  bus.emit('statusChanged', { key, value, error });
}
