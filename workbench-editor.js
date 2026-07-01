/** endgame-ai workbench - Wiring editor (hybrid JSON + form) */
class WiringEditor {
  constructor(container, api, state) {
    this.container = container;
    this.api = api;
    this.state = state;
    this.currentWiring = null;
    this.mode = 'form'; // 'form' or 'json'
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <div class="wiring-editor">
        <div class="editor-toolbar">
          <div class="tabs" role="tablist">
            <button class="tab active" role="tab" data-mode="form">Form Editor</button>
            <button class="tab" role="tab" data-mode="json">JSON Editor</button>
          </div>
          <div class="toolbar-actions">
            <button class="btn btn-secondary" id="wiring-refresh">Refresh</button>
            <button class="btn btn-primary" id="wiring-save">Save</button>
          </div>
        </div>
        <div class="editor-content">
          <div class="editor-pane form-pane" data-pane="form"></div>
          <div class="editor-pane json-pane" data-pane="json" style="display:none;">
            <textarea id="wiring-json" class="json-textarea" spellcheck="false"></textarea>
          </div>
        </div>
      </div>
    `;
    this.bindEvents();
  }

  bindEvents() {
    this.container.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => this.switchMode(tab.dataset.mode));
    });
    this.container.querySelector('#wiring-refresh').addEventListener('click', () => this.load());
    this.container.querySelector('#wiring-save').addEventListener('click', () => this.save());
  }

  switchMode(mode) {
    this.mode = mode;
    this.container.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.mode === mode));
    this.container.querySelectorAll('.editor-pane').forEach(p => p.style.display = p.dataset.pane === mode ? 'block' : 'none');
    
    if (mode === 'json' && this.currentWiring) {
      this.container.querySelector('#wiring-json').value = JSON.stringify(this.currentWiring, null, 2);
    }
  }

  async load() {
    try {
      const data = await this.api.get('/api/wiring');
      this.currentWiring = data;
      this.state.set('wiring', data);
      if (this.mode === 'form') {
        this.renderForm(data);
      } else {
        this.container.querySelector('#wiring-json').value = JSON.stringify(data, null, 2);
      }
      this.showToast('Wiring loaded', 'success');
    } catch (e) {
      this.showToast(`Failed to load wiring: ${e.message}`, 'error');
    }
  }

  async save() {
    try {
      let wiring = this.currentWiring;
      if (this.mode === 'json') {
        const jsonText = this.container.querySelector('#wiring-json').value;
        wiring = JSON.parse(jsonText);
      } else {
        wiring = this.collectFormData();
      }
      const result = await this.api.post('/api/wiring', wiring);
      this.currentWiring = wiring;
      this.state.set('Wiring = wiring;
      this.showToast('Wiring saved successfully', 'success');
    } catch (e) {
      this.showToast(`Failed to save: ${e.message}`, 'error');
    }
  }

  renderForm(wiring) {
    const pane = this.container.querySelector('.form-pane');
    const model = wiring.model || {};
    const transport = model.transport || 'openai';
    const transportConfig = model.transport_config?.[transport] || {};
    
    pane.innerHTML = `
      <div class="form-section">
        <h3>Transport Selection</h3>
        <div class="form-group">
          <label>Transport</label>
          <select id="wiring-transport">
            ${Object.keys(model.transport_config || {}).map(t => 
              `<option value="${t}" ${t === transport ? 'selected' : ''}>${t}</option>`
            ).join('')}
          </select>
        </div>
      </div>
      
      <div class="form-section">
        <h3>Transport Config: ${transport}</h3>
        <div id="transport-config-form"></div>
      </div>
      
      <div class="form-section">
        <h3>Global Config</h3>
        <div id="global-config-form"></div>
      </div>
      
      <div class="form-section">
        <h3>Topology</h3>
        <div id="topology-form"></div>
      </div>
    `;
    
    this.renderTransportConfig(transportConfig);
    this.renderGlobalConfig(model.global || {});
    this.renderTopology(wiring.topology || {});
    
    // Transport change handler
    this.container.querySelector('#wiring-transport').addEventListener('change', (e) => {
      const newTransport = e.target.value;
      const newConfig = model.transport_config?.[newTransport] || {};
      this.renderTransportConfig(newConfig);
    });
  }

  renderTransportConfig(config) {
    const container = this.container.querySelector('#transport-config-form');
    const reasoning = config.reasoning || {};
    
    container.innerHTML = `
      ${this.renderConfigFields(config, ['executable', 'model', 'base_url', 'path', 'api_key_env', 'url', 'mode', 'request_path', 'response_path', 'poll_interval', 'extra_args'])}
      
      <details class="reasoning-config" open>
        <summary>Reasoning Configuration</summary>
        <div class="form-group">
          <label>Enabled</label>
          <input type="checkbox" id="reasoning-enabled" ${reasoning.enabled !== false ? 'checked' : ''}>
        </div>
        <div class="form-group">
          <label>Pattern</label>
          <select id="reasoning-pattern">
            <option value="two_pass" ${reasoning.pattern === 'two_pass' ? 'selected' : ''}>Two Pass</option>
            <option value="single_pass" ${reasoning.pattern === 'single_pass' ? 'selected' : ''}>Single Pass</option>
            <option value="native" ${reasoning.pattern === 'native' ? 'selected' : ''}>Native</option>
            <option value="custom" ${reasoning.pattern === 'custom' ? 'selected' : ''}>Custom</option>
          </select>
        </div>
        <div class="form-group">
          <label>Injection Template</label>
          <input type="text" id="reasoning-template" value="${(reasoning.injection_template || 'ROD_REASONING_CONTENT:\\n{reasoning}').replace(/"/g, '"')}">
        </div>
        <div class="form-group">
          <label>Extractor</label>
          <select id="reasoning-extractor">
            <option value="think_tags" ${reasoning.extractor === 'think_tags' ? 'selected' : ''}>Think Tags</option>
            <option value="reasoning_field" ${reasoning.extractor === 'reasoning_field' ? 'selected' : ''}>Reasoning Field</option>
          </select>
        </div>
      </details>
    `;
  }

  renderGlobalConfig(global) {
    const container = this.container.querySelector('#global-config-form');
    container.innerHTML = `
      <div class="form-group">
        <label>Timeout (s)</label>
        <input type="number" id="global-timeout" value="${global.timeout || 180}" min="1">
      </div>
      <div class="form-group">
        <label>Max Brain Calls</label>
        <input type="number" id="global-max-calls" value="${global.max_brain_calls || ''}" min="1" placeholder="unlimited">
      </div>
      <div class="form-group">
        <label>Raw Log</label>
        <input type="checkbox" id="global-raw-log" ${global.raw_log !== false ? 'checked' : ''}>
      </div>
      <div class="form-group">
        <label>Reasoning Enabled (Global)</label>
        <input type="checkbox" id="global-reasoning" ${global.reasoning_enabled !== false ? 'checked' : ''}>
      </div>
    `;
  }

  renderTopology(topology) {
    const container = this.container.querySelector('#topology-form');
    const nodes = topology.nodes || [];
    const edges = topology.edges || {};
    
    container.innerHTML = `
      <div class="form-group">
        <label>Cycle Start</label>
        <select id="topology-cycle-start">
          ${nodes.map(n => `<option value="${n}" ${n === topology.cycle_start ? 'selected' : ''}>${n}</option>`).join('')}
        </select>
      </div>
      <details open>
        <summary>Nodes (${nodes.length})</summary>
        <div id="topology-nodes">${nodes.map(n => `<span class="badge badge-info" style="margin:2px;">${n}</span>`).join('')}</div>
      </details>
      <details open>
        <summary>Edges</summary>
        <div class="code-block" style="max-height:200px;">${JSON.stringify(edges, null, 2)}</div>
      </details>
    `;
  }

  renderConfigFields(config, fields) {
    return fields.map(field => {
      if (!(field in config)) return '';
      const value = config[field];
      const type = Array.isArray(value) ? 'array' : typeof value;
      let input;
      
      if (type === 'boolean') {
        input = `<input type="checkbox" id="cfg-${field}" ${value ? 'checked' : ''}>`;
      } else if (type === 'array') {
        input = `<textarea id="cfg-${field}" rows="3">${value.join('\\n')}</textarea>`;
      } else {
        input = `<input type="text" id="cfg-${field}" value="${String(value).replace(/"/g, '"')}">`;
      }
      
      return `
        <div class="form-group">
          <label>${field}</label>
          ${input}
        </div>
      `;
    }).join('');
  }

  collectFormData() {
    // Simplified - in real implementation would collect all form fields
    return this.currentWiring;
  }

  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }
}

export { WiringEditor };