// js/state.js — shared application state + lightweight event bus

const _listeners = {};

export const bus = {
  on(event, fn)  { (_listeners[event] = _listeners[event] || []).push(fn); },
  off(event, fn) { _listeners[event] = (_listeners[event] || []).filter(f => f !== fn); },
  emit(event, data) { (_listeners[event] || []).forEach(fn => fn(data)); }
};

export const state = {
  metric: 'enrollment',
  enrollmentField: 'total_medicaid_and_chip_enrollment',
  pmpmCategory:    'total',
  geo: { type: 'all', label: 'All States', states: null },
  perCapita: false,
  fromYear: null,
  snapshotPeriod:    null,
  changeStartPeriod: null,
  changeEndPeriod:   null,
  enrollmentByState:  null,
  enrollmentByPeriod: null,
  managedCareData:    null,
  pmpmData:           null,
  availablePeriods: [],
  latestPeriod:     null,
  earliestPeriod:   null,
  columnMap:        null,
  status: {
    enrollment:   'pending',
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
