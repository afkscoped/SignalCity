// static/js/xai.js — Explainable AI panel management

export class XAI {
  constructor() {
    this.textEl = document.getElementById('xaiText');
    this.summaryEl = document.getElementById('xaiSummary');
    this.stepCounterEl = document.getElementById('stepCounter');
    this.stepCount = 0;
    this.totalEstimate = 0;
  }

  update(xaiText, stats) {
    this.stepCount++;
    if (this.textEl) {
      this.textEl.style.opacity = '0';
      setTimeout(() => {
        this.textEl.textContent = xaiText || '';
        this.textEl.style.opacity = '1';
      }, 100);
    }
    if (this.stepCounterEl) {
      const est = this.totalEstimate || stats?.theoretical_n || '?';
      this.stepCounterEl.textContent = `Step ${this.stepCount} of ~${est}`;
    }
  }

  showSummary(summaryText) {
    if (this.summaryEl) {
      this.summaryEl.textContent = summaryText || '';
      this.summaryEl.classList.remove('hidden');
    }
    if (this.stepCounterEl) {
      this.stepCounterEl.textContent = `Complete — ${this.stepCount} steps`;
    }
  }

  reset() {
    this.stepCount = 0;
    if (this.textEl) this.textEl.textContent = 'Run an algorithm to see step-by-step explanations here.';
    if (this.summaryEl) { this.summaryEl.textContent = ''; this.summaryEl.classList.add('hidden'); }
    if (this.stepCounterEl) this.stepCounterEl.textContent = 'Step 0';
  }

  setEstimate(n) {
    this.totalEstimate = n;
  }
}
