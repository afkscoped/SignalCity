// static/js/analytics.js — Run tracking and JSON export

export class Analytics {
  constructor() {
    this.runs = [];
    this.currentRun = null;
    this.sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2,8)}`;
  }

  startRun(algoName, cityId) {
    this.currentRun = {
      algorithm: algoName,
      city_id: cityId,
      started_at: Date.now(),
      steps: [],
      summary: null,
    };
  }

  recordStep(delta) {
    if (!this.currentRun) return;
    this.currentRun.steps.push({
      kind: delta.kind,
      timestamp: Date.now(),
      op_count: delta.op_count || 0,
      xai_text: delta.xai_text || '',
    });
  }

  endRun(summary) {
    if (!this.currentRun) return;
    this.currentRun.summary = summary;
    this.currentRun.ended_at = Date.now();
    this.currentRun.duration_ms = this.currentRun.ended_at - this.currentRun.started_at;
    this.runs.push(this.currentRun);
    this.currentRun = null;
  }

  exportJSON() {
    const data = {
      session_id: this.sessionId,
      exported_at: new Date().toISOString(),
      total_runs: this.runs.length,
      runs: this.runs.map(r => ({
        algorithm: r.algorithm,
        city_id: r.city_id,
        duration_ms: r.duration_ms,
        total_steps: r.steps.length,
        summary: r.summary,
      })),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `signal_city_analytics_${this.sessionId}.json`;
    a.click();
    URL.revokeObjectURL(url);

    window.game?.showToast('Analytics exported!', 'success');
  }

  getStats() {
    return {
      total_runs: this.runs.length,
      total_steps: this.runs.reduce((s, r) => s + r.steps.length, 0),
      algorithms_used: [...new Set(this.runs.map(r => r.algorithm))],
    };
  }
}
