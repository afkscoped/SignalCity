// static/js/hud.js — All HUD panels: complexity dashboard, Gantt chart, flow minimap

export class HUD {
  constructor() {
    // Cache DOM refs
    this.els = {};
    ['algoStatus','algoNameDisplay','statOps','statNodes','statEdges','statFrontier','statWall','statMem',
     'complexityLabel','complexityRatio','complexityBar','comparisonRow',
     'resCredits','resGold','resHappy','resPop',
     'ganttTotal','ganttMissed','ganttRate','ganttAvg','flowTotal'].forEach(id => {
      this.els[id] = document.getElementById(id);
    });

    this._ganttData = [];
    this._flowData = { total: 0, edges: [] };
    this._startTime = 0;
  }

  startAlgo(name) {
    this._startTime = performance.now();
    this._ganttData = [];
    if (this.els.algoNameDisplay) this.els.algoNameDisplay.textContent = name;
    if (this.els.algoStatus) { this.els.algoStatus.textContent = 'Running'; this.els.algoStatus.className = 'badge badge-running'; }
  }

  update(stats) {
    if (!stats) return;
    const wallMs = Math.round(performance.now() - this._startTime);
    const ops = stats.ops_so_far || 0;
    const memKB = Math.round((stats.nodes_visited || 0) * 64 + ops * 16) / 1024;

    this._set('statOps', this._formatNum(ops));
    this._set('statNodes', this._formatNum(stats.nodes_visited || 0));
    this._set('statEdges', this._formatNum(stats.edges_added || 0));
    this._set('statFrontier', stats.frontier_size || '—');
    this._set('statWall', wallMs > 1000 ? `${(wallMs/1000).toFixed(1)}s` : `${wallMs}ms`);
    this._set('statMem', memKB > 1024 ? `${(memKB/1024).toFixed(1)}MB` : `${Math.round(memKB)}KB`);

    // Complexity bar
    if (stats.theoretical_complexity) this._set('complexityLabel', stats.theoretical_complexity);
    const theoretical = stats.theoretical_n ? stats.theoretical_n * Math.log2(Math.max(stats.theoretical_n, 2)) : ops * 2;
    const ratio = Math.min(ops / Math.max(theoretical, 1), 1);
    const pct = Math.round(ratio * 100);
    this._set('complexityRatio', `${pct}%`);
    if (this.els.complexityBar) {
      this.els.complexityBar.style.width = `${pct}%`;
      this.els.complexityBar.className = `progress-fill${pct > 95 ? ' danger' : pct > 80 ? ' warning' : ''}`;
    }
  }

  showSummary(summary) {
    if (this.els.algoStatus) { this.els.algoStatus.textContent = 'Complete ✓'; this.els.algoStatus.className = 'badge badge-complete'; }
    // Flash green
    const panel = document.getElementById('hudPanel');
    if (panel) {
      panel.style.boxShadow = '0 0 30px rgba(29,158,117,0.4)';
      setTimeout(() => panel.style.boxShadow = '', 1500);
    }
  }

  updateResources(profile) {
    if (!profile) return;
    this._set('resCredits', profile.compute_credits || 100);
    this._set('resGold', profile.coins || 0);
    this._set('resHappy', (profile.happiness || 50) + '%');
    this._set('resPop', profile.population || 100);
  }

  updateGantt(delta) {
    if (!delta.job_id) return;
    this._ganttData.push(delta);
    this._renderGantt();

    // Update stats
    const total = new Set(this._ganttData.filter(d => d.kind==='job_complete').map(d => d.job_id)).size;
    const missed = this._ganttData.filter(d => d.kind==='job_complete' && d.deadline_missed).length;
    this._set('ganttTotal', total);
    this._set('ganttMissed', missed);
    this._set('ganttRate', total > 0 ? Math.round(missed/total*100)+'%' : '0%');

    const completes = this._ganttData.filter(d => d.kind==='job_complete');
    if (completes.length > 0) {
      const avgTurn = completes.reduce((s,d) => s + (d.end_time - d.start_time), 0) / completes.length;
      this._set('ganttAvg', avgTurn.toFixed(1));
    }

    // Show panel
    document.getElementById('ganttPanel').style.display = 'block';
  }

  updateFlow(delta) {
    this._flowData.total = delta.total_flow || 0;
    this._set('flowTotal', Math.round(this._flowData.total));
    document.getElementById('flowPanel').style.display = 'block';
    this._renderFlow(delta);
  }

  _renderGantt() {
    const svg = d3.select('#ganttChart');
    svg.selectAll('*').remove();

    const data = this._ganttData.filter(d => d.start_time !== undefined && d.end_time !== undefined);
    if (data.length === 0) return;

    const jobIds = [...new Set(data.map(d => d.job_id))];
    const maxTime = Math.max(...data.map(d => d.end_time || 0)) + 1;

    const x = d3.scaleLinear().domain([0, maxTime]).range([55, 610]);
    const y = d3.scaleBand().domain(jobIds).range([15, 170]).padding(0.15);

    // Axis
    svg.append('g').attr('transform', 'translate(0,170)')
      .call(d3.axisBottom(x).ticks(8).tickSize(-155))
      .selectAll('text').attr('fill', '#6B7280').attr('font-size', '8px');
    svg.selectAll('.domain,.tick line').attr('stroke', 'rgba(255,255,255,0.05)');

    // Y labels
    svg.selectAll('.job-label').data(jobIds).enter()
      .append('text').attr('x', 50).attr('y', d => y(d) + y.bandwidth()/2 + 3)
      .attr('text-anchor', 'end').attr('fill', '#6B7280').attr('font-size', '7px')
      .text(d => d.replace('citizen_', 'C'));

    // Bars
    data.forEach(d => {
      const color = d.deadline_missed ? '#E24B4A' : '#1D9E75';
      svg.append('rect')
        .attr('class', 'gantt-bar')
        .attr('x', x(d.start_time)).attr('y', y(d.job_id))
        .attr('width', Math.max(2, x(d.end_time) - x(d.start_time)))
        .attr('height', y.bandwidth())
        .attr('fill', color).attr('opacity', 0.8);

      // Deadline marker
      if (d.deadline) {
        svg.append('line')
          .attr('x1', x(d.deadline)).attr('x2', x(d.deadline))
          .attr('y1', y(d.job_id)).attr('y2', y(d.job_id) + y.bandwidth())
          .attr('stroke', '#EF9F27').attr('stroke-width', 1.5)
          .attr('stroke-dasharray', '3,2');
      }
    });
  }

  _renderFlow(delta) {
    const svg = d3.select('#flowChart');
    svg.selectAll('*').remove();

    if (!delta.path) return;

    // Simple path visualization
    const pathNodes = delta.path || [];
    if (pathNodes.length < 2) return;

    const n = pathNodes.length;
    const cx = 120, cy = 80, r = 60;

    pathNodes.forEach((nodeId, i) => {
      const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
      const nx = cx + Math.cos(angle) * r;
      const ny = cy + Math.sin(angle) * r;

      // Edge to next
      if (i < n - 1) {
        const nextAngle = ((i + 1) / n) * Math.PI * 2 - Math.PI / 2;
        const nnx = cx + Math.cos(nextAngle) * r;
        const nny = cy + Math.sin(nextAngle) * r;
        svg.append('line')
          .attr('x1', nx).attr('y1', ny).attr('x2', nnx).attr('y2', nny)
          .attr('stroke', '#1D9E75').attr('stroke-width', 2).attr('opacity', 0.6);
      }

      // Node
      const isSource = i === 0;
      const isSink = i === n - 1;
      svg.append('circle')
        .attr('cx', nx).attr('cy', ny).attr('r', isSource || isSink ? 8 : 5)
        .attr('fill', isSource ? '#1D9E75' : isSink ? '#E24B4A' : '#378ADD');

      if (isSource || isSink) {
        svg.append('text')
          .attr('x', nx).attr('y', ny + 3)
          .attr('text-anchor', 'middle').attr('fill', 'white').attr('font-size', '8px').attr('font-weight', 'bold')
          .text(isSource ? 'S' : 'T');
      }
    });

    // Total flow label
    svg.append('text')
      .attr('x', 120).attr('y', 155)
      .attr('text-anchor', 'middle').attr('fill', '#6B7280').attr('font-size', '9px')
      .text(`Flow: ${Math.round(delta.total_flow || 0)} vehicles/hr`);
  }

  reset() {
    ['statOps','statNodes','statEdges','statFrontier'].forEach(id => this._set(id, '0'));
    this._set('statWall', '0ms');
    this._set('statMem', '0KB');
    this._set('complexityRatio', '0%');
    if (this.els.complexityBar) this.els.complexityBar.style.width = '0%';
    if (this.els.algoStatus) { this.els.algoStatus.textContent = 'Idle'; this.els.algoStatus.className = 'badge badge-idle'; }
    this._set('algoNameDisplay', '—');
    this._ganttData = [];

    document.getElementById('ganttPanel').style.display = 'none';
    document.getElementById('flowPanel').style.display = 'none';
  }

  _set(id, val) {
    if (this.els[id]) this.els[id].textContent = val;
  }

  _formatNum(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toString();
  }
}
