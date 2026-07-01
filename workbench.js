/** endgame-ai workbench - Main application */
import { api } from './workbench-api.js';
import { state } from './workbench-state.js';
import { TopologyGraph } from './workbench-graph.js';
import { WiringEditor } from './workbench-editor.js';

class WorkbenchApp {
  constructor() {
    this.graph = null;
    this.editor = null;
    this.pollInterval = null;
    this.logPollInterval = null;
    this.init();
  }

  async init() {
    // Initialize components
    this.graph = new TopologyGraph(document.getElementById('topology-graph'));
    this.editor = new WiringEditor(document.getElementById('wiring-editor'), api, state);
    
    // Bind UI events
    this.bindEvents();
    
    // Initial load
    await this.refreshAll();
    
    // Start polling
    this.startPolling();
  }

  bindEvents() {
    // Control buttons
    document.getElementById('btn-run').addEventListener('click', () => this.setControl('run'));
    document.getElementById('btn-pause').addEventListener('click', () => this.setControl('pause'));
    document.getElementById('btn-step').addEventListener('click', () => this.setControl('step'));
    
    // Transport probe
    document.getElementById('btn-probe').addEventListener('click', () => this.probeTransport());
    
    // Brain test
    document.getElementById('btn-test').addEventListener('click', () => this.runBrainTest());
    
    // Refresh wiring
    document.getElementById('btn-refresh-wiring').addEventListener('click', () => this.editor.load());
    
    // Log lines input
    document.getElementById('log-lines').addEventListener('change', () => this.refreshLogs());
    
    // State subscriptions
    state.on('organism', (data) => this.updateOrganismUI(data));
    state.on('control', (data) => this.updateControlUI(data));
    state.on('wiring', (data) => this.updateWiringUI(data));
    state.on('runtime', (data) => this.updateRuntimeUI(data));
  }

  async refreshAll() {
    try {
      const [status, wiring] = await Promise.all([
        api.get('/api/status'),
        api.get('/api/wiring'),
      ]);
      
      if (status.ok) {
        state.set('organism', status.state);
        state.set('control', status.control);
        state.set('runtime', status.runtime_tail || []);
        state.set('wiring', status.wiring);
      }
      
      state.set('wiring', wiring);
      
      await this.refreshLogs();
    } catch (e) {
      console.error('Failed to refresh:', e);
      this.showToast(`Refresh failed: ${e.message}`, 'error');
    }
  }

  async refreshLogs() {
    try {
      const lines = parseInt(document.getElementById('log-lines').value) || 100;
      const data = await api.get(`/api/logs/tail?lines=${lines}`);
      if (data.ok) {
        state.set('logs', data.logs);
        this.updateLogsUI(data.logs);
      }
    } catch (e) {
      console.error('Failed to refresh logs:', e);
    }
  }

  async setControl(mode) {
    try {
      const result = await api.post('/api/control', { mode });
      if (result.ok) {
        state.set('control', result.control);
        this.showToast(`Control set to ${mode}`, 'success');
      }
    } catch (e) {
      this.showToast(`Control failed: ${e.message}`, 'error');
    }
  }

  async probeTransport() {
    const btn = document.getElementById('btn-probe');
    btn.disabled = true;
    btn.textContent = 'Probing...';
    
    try {
      const result = await api.get('/api/transport/probe');
      this.updateTransportProbeUI(result);
      this.showToast(result.ok ? 'Transport healthy' : `Transport issue: ${result.error}`, result.ok ? 'success' : 'warning');
    } catch (e) {
      this.showToast(`Probe failed: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Probe Transport';
    }
  }

  async runBrainTest() {
    const btn = document.getElementById('btn-test');
    const transportSelect = document.getElementById('test-transport');
    const transport = transportSelect.value;
    
    btn.disabled = true;
    btn.textContent = 'Testing...';
    
    try {
      const result = await api.post('/api/brain/test', { transport });
      this.updateBrainTestUI(result);
      this.showToast(result.ok ? 'ROD test passed' : `ROD test failed: ${result.error}`, result.ok ? 'success' : 'error');
    } catch (e) {
      this.showToast(`Test failed: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Run ROD Test';
    }
  }

  startPolling() {
    // Status polling every 1s
    this.pollInterval = setInterval(() => this.refreshAll(), 1000);
    
    // Log polling every 5s
    this.logPollInterval = setInterval(() => this.refreshLogs(), 5000);
  }

  stopPolling() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    if (this.logPollInterval) clearInterval(this.logPollInterval);
  }

  updateOrganismUI(data) {
    if (!data) return;
    
    // Update status cards
    this.setText('phase', data._phase || '—');
    this.setText('node', data.current_node || '—');
    this.setText('next-node', data.next_node || '—');
    this.setText('tick', data.tick || 0);
    this.setText('goal', data.goal || '(none)');
    this.setText('transport', data.wiring_transport || '—');
    this.setText('last-error', data.last_error || 'none');
    
    // Update phase pill
    const phaseEl = document.getElementById('phase-pill');
    if (phaseEl) {
      phaseEl.textContent = `phase: ${data._phase || '—'}`;
      phaseEl.className = 'pill ' + this.getPhaseClass(data._phase);
    }
    
    // Update graph
    if (this.graph && state.get('wiring')) {
      this.graph.update({
        topology: state.get('wiring').topology,
        state: data,
      });
    }
  }

  updateControlUI(data) {
    if (!data) return;
    this.setText('control-mode', data.mode);
    this.setText('step-token', data.step_token);
    
    // Update button states
    document.getElementById('btn-run').classList.toggle('active', data.mode === 'run');
    document.getElementById('btn-pause').classList.toggle('active', data.mode === 'pause');
  }

  updateWiringUI(data) {
    if (!data) return;
    this.editor.currentWiring = data;
    if (this.editor.mode === 'form') {
      this.editor.renderForm(data);
    }
    
    // Update transport select for brain test
    const select = document.getElementById('test-transport');
    if (select) {
      const currentTransport = data.model?.transport;
      select.innerHTML = Object.keys(data.model?.transport_config || {}).map(t => 
        `<option value="${t}" ${t === currentTransport ? 'selected' : ''}>${t}</option>`
      ).join('');
    }
  }

  updateRuntimeUI(events) {
    const container = document.getElementById('runtime-events');
    if (!container) return;
    
    container.innerHTML = events.slice().reverse().map(e => `
      <div class="runtime-event">
        <span class="event-time">${new Date(e.ts * 1000).toLocaleTimeString()}</span>
        <span class="event-type ${this.getEventClass(e.event)}">${e.event}</span>
        <span class="event-node">${e.node || ''}</span>
        <span class="event-signal">${e.signal || ''}</span>
      </div>
    `).join('');
  }

  updateLogsUI(logs) {
    const container = document.getElementById('logs-content');
    if (!container) return;
    
    container.innerHTML = logs.map(log => `
      <div class="log-entry">
        <pre>${this.escapeHtml(JSON.stringify(log, null, 2))}</pre>
      </div>
    `).join('');
  }

  updateTransportProbeUI(result) {
    const container = document.getElementById('probe-result');
    if (!container) return;
    
    container.innerHTML = `
      <div class="probe-result ${result.ok ? 'ok' : 'err'}">
        <pre>${this.escapeHtml(JSON.stringify(result, null, 2))}</pre>
      </div>
    `;
  }

  updateBrainTestUI(result) {
    const container = document.getElementById('test-result');
    if (!container) return;
    
    container.innerHTML = `
      <div class="test-result ${result.ok ? 'ok' : 'err'}">
        <pre>${this.escapeHtml(JSON.stringify(result, null, 2))}</pre>
      </div>
    `;
  }

  getPhaseClass(phase) {
    if (!phase) return '';
    if (phase === 'executing_node' || phase === 'node_start') return 'warn';
    if (phase === 'error' || phase === 'halted') return 'err';
    if (phase === 'max_ticks' || phase === 'interrupted') return 'warn';
    return 'ok';
  }

  getEventClass(event) {
    if (!event) return '';
    if (event.includes('error')) return 'err';
    if (event.includes('start') || event.includes('complete')) return 'warn';
    return 'ok';
  }

  setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.workbenchApp = new WorkbenchApp();
});