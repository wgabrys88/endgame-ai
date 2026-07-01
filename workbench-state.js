/** endgame-ai workbench - State management */
class WorkbenchState {
  constructor() {
    this.state = {
      organism: null,
      control: null,
      wiring: null,
      runtime: [],
      logs: [],
      activeNode: null,
      selectedTransport: null,
      wiringEditor: null,
      isPolling: false,
      pollInterval: null,
      logPollInterval: null,
    };
    this.listeners = new Map();
  }

  set(key, value) {
    this.state[key] = value;
    this.emit(key, value);
  }

  get(key) {
    return this.state[key];
  }

  getAll() {
    return { ...this.state };
  }

  on(key, callback) {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key).add(callback);
    // Immediately call with current value
    if (this.state[key] !== undefined) {
      callback(this.state[key]);
    }
    return () => this.off(key, callback);
  }

  off(key, callback) {
    const listeners = this.listeners.get(key);
    if (listeners) {
      listeners.delete(callback);
    }
  }

  emit(key, value) {
    const listeners = this.listeners.get(key);
    if (listeners) {
      listeners.forEach(cb => cb(value));
    }
  }
}

const state = new WorkbenchState();
export { state, WorkbenchState };