/** endgame-ai workbench - Topology graph visualization */
class TopologyGraph {
  constructor(container) {
    this.container = container;
    this.nodes = [];
    this.edges = [];
    this.activeNode = null;
    this.width = 0;
    this.height = 0;
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <svg class="topology-svg" viewBox="0 0 800 500" preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#4a9eff" />
          </marker>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        <g class="edges-layer"></g>
        <g class="nodes-layer"></g>
      </svg>
    `;
    this.svg = this.container.querySelector('svg');
    this.edgesLayer = this.svg.querySelector('.edges-layer');
    this.nodesLayer = this.svg.querySelector('.nodes-layer');
  }

  update(data) {
    if (!data || !data.topology) return;
    
    this.nodes = data.topology.nodes || [];
    this.edges = this.buildEdges(data.topology.edges || {});
    this.activeNode = data.state?.current_node || null;
    this.layout();
    this.draw();
  }

  buildEdges(edges) {
    const result = [];
    for (const [from, targets] of Object.entries(edges)) {
      for (const [signal, to] of Object.entries(targets)) {
        result.push({ from, to, signal });
      }
    }
    return result;
  }

  layout() {
    // Circular layout
    const centerX = 400;
    const centerY = 250;
    const radius = Math.min(centerX, centerY) - 60;
    const nodeCount = this.nodes.length;
    
    this.nodePositions = {};
    
    if (nodeCount === 0) return;
    
    // Place cycle_start at top if it exists
    const cycleStart = this.nodes[0]; // Use first node as reference
    const startIndex = this.nodes.indexOf(cycleStart);
    
    this.nodes.forEach((node, i) => {
      const angle = ((i - startIndex) / nodeCount) * 2 * Math.PI - Math.PI / 2;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      this.nodePositions[node] = { x, y };
    });
  }

  draw() {
    // Draw edges
    this.edgesLayer.innerHTML = '';
    this.edges.forEach(edge => {
      const fromPos = this.nodePositions[edge.from];
      const toPos = this.nodePositions[edge.to];
      if (!fromPos || !toPos) return;
      
      const path = this.createEdgePath(fromPos, toPos);
      path.classList.add('edge-path');
      if (edge.from === this.activeNode) {
        path.classList.add('active');
      }
      path.setAttribute('marker-end', 'url(#arrowhead)');
      this.edgesLayer.appendChild(path);
      
      // Signal label
      const midX = (fromPos.x + toPos.x) / 2;
      const midY = (fromPos.y + toPos.y) / 2;
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.className = 'node-signal';
      label.setAttribute('x', midX);
      label.setAttribute('y', midY - 5);
      label.setAttribute('text-anchor', 'middle');
      label.textContent = edge.signal;
      this.edgesLayer.appendChild(label);
    });
    
    // Draw nodes
    this.nodesLayer.innerHTML = '';
    this.nodes.forEach(node => {
      const pos = this.nodePositions[node];
      if (!pos) return;
      
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.className = 'node-group';
      g.style.cursor = 'pointer';
      
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.className = 'node-circle';
      circle.setAttribute('cx', pos.x);
      circle.setAttribute('cy', pos.y);
      circle.setAttribute('r', 28);
      circle.setAttribute('fill', this.getNodeColor(node));
      circle.setAttribute('stroke', this.getNodeStroke(node));
      circle.setAttribute('stroke-width', node === this.activeNode ? 3 : 1.5);
      
      if (node === this.activeNode) {
        circle.classList.add('active');
        circle.setAttribute('filter', 'url(#glow)');
      }
      
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.className = 'node-label';
      label.setAttribute('x', pos.x);
      label.setAttribute('y', pos.y + 4);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('dominant-baseline', 'middle');
      label.textContent = node;
      
      g.appendChild(circle);
      g.appendChild(label);
      this.nodesLayer.appendChild(g);
    });
  }

  createEdgePath(from, to) {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    
    // Shorten path to not overlap nodes
    const nodeRadius = 30;
    const factor = (dist - 2 * nodeRadius) / dist;
    const startX = from.x + dx * (1 - factor) / 2;
    const startY = from.y + dy * (1 - factor) / 2;
    const endX = to.x - dx * (1 - factor) / 2;
    const endY = to.y - dy * (1 - factor) / 2;
    
    // Check if we need a curved path (for loops or close nodes)
    const midX = (startX + endX) / 2;
    const midY = (startY + endY) / 2;
    const perpX = -dy / dist * 40;
    const perpY = dx / dist * 40;
    
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    
    if (dist < 120) {
      // Curved path for close nodes
      path.setAttribute('d', `M${startX},${startY} Q${midX + perpX},${midY + perpY} ${endX},${endY}`);
    } else {
      // Straight path
      path.setAttribute('d', `M${startX},${startY} L${endX},${endY}`);
    }
    
    path.setAttribute('stroke', '#4a9eff');
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('fill', 'none');
    path.setAttribute('opacity', '0.7');
    
    return path;
  }

  getNodeColor(node) {
    const colors = {
      planner: '#2a5a8a',
      observe: '#1a5a3a',
      decide: '#5a4a1a',
      act: '#5a1a3a',
      verify: '#1a4a5a',
      reflect: '#4a1a5a',
      self_modify: '#5a2a1a',
      error: '#5a1a1a',
    };
    return colors[node] || '#2a3a4a';
  }

  getNodeStroke(node) {
    const strokes = {
      planner: '#4a9eff',
      observe: '#4ade80',
      decide: '#fbbf24',
      act: '#fb7185',
      verify: '#22d3ee',
      reflect: '#c084fc',
      self_modify: '#fb923c',
      error: '#fb7185',
    };
    return strokes[node] || '#5a6a7a';
  }
}

export { TopologyGraph };