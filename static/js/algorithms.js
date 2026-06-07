// static/js/algorithms.js — WebSocket client + animation coordinator

export class AlgorithmRunner {
  constructor(scene) {
    this.scene = scene;
    this.graph = null;
    this.ws = null;
    this._stepLog = [];
    this._stepIndex = 0;
    this._paused = false;
    this._manualMode = false;
    this._onStep = null;
    this._onComplete = null;
  }

  setGraph(graph) {
    this.graph = graph;
  }

  async run(algoName, { speed_ms = 120, onStep, onComplete, cityId = 'bangalore', params = {} }) {
    this.stop();
    this._stepLog = [];
    this._stepIndex = 0;
    this._onStep = onStep;
    this._onComplete = onComplete;

    // Reset city visuals
    window.game?.cityBuilder?.resetStates();

    return new Promise((resolve, reject) => {
      try {
        const wsUrl = `ws://${window.location.host}/ws/algorithm`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          this.ws.send(JSON.stringify({
            action: 'run',
            algorithm: algoName,
            city_id: cityId,
            params: { speed_ms, ...params },
          }));
        };

        this.ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);

            if (msg.type === 'step') {
              const delta = msg.delta;
              const stats = msg.stats;
              this._stepLog.push(delta);
              this._stepIndex = this._stepLog.length;

              if (!this._paused && !this._manualMode) {
                this._animateDelta(delta);
                if (this._onStep) this._onStep(delta, stats);
              }
            } else if (msg.type === 'complete') {
              const summary = msg.summary;
              this._animateCompletion(summary);
              if (this._onComplete) this._onComplete(summary);
              resolve(summary);
            } else if (msg.type === 'error') {
              window.game?.showToast(msg.message || 'Algorithm error', 'error');
              reject(new Error(msg.message));
            }
          } catch (e) {
            console.error('WS message parse error:', e);
          }
        };

        this.ws.onerror = (err) => {
          console.error('WS error:', err);
          window.game?.showToast('Connection error. Is the server running?', 'error');
          reject(err);
        };

        this.ws.onclose = () => {
          this.ws = null;
        };
      } catch (e) {
        reject(e);
      }
    });
  }

  _animateDelta(delta) {
    const city = window.game?.cityBuilder;
    if (!city) return;

    const kind = delta.kind;

    switch (kind) {
      case 'edge_added': {
        city.setEdgeState(delta.from_node, delta.to_node, 'added');
        const pos = city.getNodePosition(delta.to_node);
        if (pos) city.spawnParticles('build', pos.x, pos.y, pos.z, 8);
        break;
      }
      case 'edge_rejected': {
        // Brief red flash then back to unvisited
        city.setEdgeState(delta.from_node, delta.to_node, 'bottleneck');
        setTimeout(() => city.setEdgeState(delta.from_node, delta.to_node, 'unvisited'), 300);
        break;
      }
      case 'node_frontier': {
        city.setNodeState(delta.node || delta.to_node || delta.from_node, 'frontier');
        if (delta.from_node !== undefined && delta.node !== undefined) {
          city.setEdgeState(delta.from_node, delta.node, 'frontier');
        }
        break;
      }
      case 'node_visited': {
        city.setNodeState(delta.node, 'visited');
        const pos = city.getNodePosition(delta.node);
        if (pos) city.spawnParticles('settle', pos.x, pos.y, pos.z, 6);
        break;
      }
      case 'edge_relaxed': {
        city.setEdgeState(delta.from_node, delta.to_node, 'relaxed');
        break;
      }
      case 'path_found': {
        if (delta.path) {
          for (let i = 0; i < delta.path.length - 1; i++) {
            setTimeout(() => {
              city.setEdgeState(delta.path[i], delta.path[i + 1], 'path');
              city.setNodeState(delta.path[i], 'path');
            }, i * 50);
          }
        }
        break;
      }
      case 'augmenting_path': {
        if (delta.path) {
          for (let i = 0; i < delta.path.length - 1; i++) {
            city.setEdgeState(delta.path[i], delta.path[i + 1], 'flow');
          }
        }
        if (delta.bottleneck_edge) {
          city.setEdgeState(delta.bottleneck_edge[0], delta.bottleneck_edge[1], 'bottleneck');
        }
        break;
      }
      case 'flow_updated': {
        // Update flow panel
        break;
      }
      case 'node_contracted': {
        city.setNodeState(delta.node, 'visited');
        const pos = city.getNodePosition(delta.node);
        if (pos) city.spawnParticles('settle', pos.x, pos.y, pos.z, 4);
        break;
      }
      case 'node_moved':
      case 'community_refined': {
        // Community detection updates handled at completion
        break;
      }
      case 'facility_placed': {
        if (delta.facility_node !== undefined) {
          city.setFacilityMarker(delta.facility_node, delta.facility_type);
          const pos = city.getNodePosition(delta.facility_node);
          if (pos) city.spawnParticles('build', pos.x, pos.y, pos.z, 20);
        }
        break;
      }
      case 'iteration_complete': {
        // PageRank — highlight top nodes
        if (delta.top_nodes) {
          for (const tn of delta.top_nodes) {
            city.setNodeState(tn.node, 'hub');
          }
        }
        break;
      }
      case 'job_start':
      case 'job_complete':
      case 'job_preempt': {
        // Scheduling — Gantt handled by HUD
        break;
      }
    }
  }

  _animateCompletion(summary) {
    const city = window.game?.cityBuilder;
    if (!city) return;

    // Handle community colors
    if (summary.communities) {
      city.setCommunityColors(summary.communities);
    }

    // Handle facility placement
    if (summary.facilities) {
      for (const fid of summary.facilities) {
        city.setFacilityMarker(fid, summary.facility_type || 'hospital');
      }
    }

    // Completion sparkles
    for (let i = 0; i < 5; i++) {
      const x = (Math.random() - 0.5) * 80;
      const z = (Math.random() - 0.5) * 80;
      city.spawnParticles('build', x, 2, z, 15);
    }
  }

  stepForward() {
    if (this._stepIndex < this._stepLog.length) {
      const delta = this._stepLog[this._stepIndex++];
      this._animateDelta(delta);
      if (this._onStep) this._onStep(delta, {});
    }
  }

  stepBackward() {
    if (this._stepIndex > 0) {
      this._stepIndex = Math.max(0, this._stepIndex - 1);
      this._replayUpTo(this._stepIndex);
    }
  }

  _replayUpTo(targetIndex) {
    window.game?.cityBuilder?.resetStates();
    for (let i = 0; i < targetIndex; i++) {
      this._animateDelta(this._stepLog[i]);
    }
  }

  pause() { this._paused = true; }
  resume() { this._paused = false; }
  setManualMode(val) { this._manualMode = val; }

  stop() {
    if (this.ws) {
      try { this.ws.close(); } catch (e) {}
      this.ws = null;
    }
    this._stepLog = [];
    this._stepIndex = 0;
  }
}
