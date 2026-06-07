// static/js/tutorial.js — 7-step interactive tutorial system

export class Tutorial {
  constructor(game) {
    this.game = game;
    this.currentStep = 0;
    this.active = false;
    this.overlay = document.getElementById('tutorialOverlay');
    this.card = document.getElementById('tutorialCard');
    this.titleEl = document.getElementById('tutorialTitle');
    this.bodyEl = document.getElementById('tutorialBody');
    this.dotsEl = document.getElementById('tutorialDots');

    this.STEPS = [
      {
        id: 'welcome', target: null,
        title: '⚔️ Welcome to SIGNAL CITY',
        body: 'You are the Architect God of a real city. Build roads, power grids, and manage traffic — all by running classic computer science algorithms in real time. Every animation you see is an actual algorithm executing step by step. This is where theory meets reality.',
      },
      {
        id: 'city', target: '#cityDropdown',
        title: '🌍 Choose Your City',
        body: 'Select a real city from the dropdown. The game fetches real road network data from OpenStreetMap. Each city has a unique graph topology that makes different algorithms more or less efficient. Try Bengaluru, London, or Tokyo!',
      },
      {
        id: 'prim', target: '#algoButtons',
        title: '⚡ Run Your First Algorithm',
        body: 'Click an algorithm button to watch it execute live on the city graph. Start with Prim\'s MST — it builds the cheapest power grid connecting every intersection. Watch amber frontiers expand and edges turn green as they join the minimum spanning tree.',
      },
      {
        id: 'xai', target: '#xaiPanel',
        title: '🧠 Understand Every Step',
        body: 'The XAI panel explains every step in plain English. It tells you WHY the algorithm chose that edge, what the frontier looks like, and how the operation count relates to theoretical complexity. Use Prev/Next buttons for manual stepping.',
      },
      {
        id: 'hud', target: '#hudPanel',
        title: '📊 Track Complexity',
        body: 'The Algorithm Monitor shows live operation counts, memory usage, and a Big-O progress bar. Compare actual operations vs theoretical bounds. Green means efficient, amber is close to theoretical, red means the graph is challenging.',
      },
      {
        id: 'resources', target: '#profileBadge',
        title: '🏆 Level Up & Earn Rewards',
        body: 'Every algorithm run earns XP and Gold. Level up to unlock advanced algorithms like Contraction Hierarchies and Leiden Community Detection. Complete quests for bonus rewards. Check your profile for progress!',
      },
      {
        id: 'advanced', target: null,
        title: '🗡️ Your Quest Awaits',
        body: 'Signal City has 10 algorithms from cutting-edge research papers. Place hospitals with k-Median, zone districts with Leiden, find hub intersections with PageRank, and build instant-routing systems with Contraction Hierarchies. Weather events will test your builds. Good luck, Architect!',
      },
    ];
  }

  start() {
    this.currentStep = 0;
    this.active = true;
    this._render();
    if (this.overlay) this.overlay.style.display = 'block';
  }

  next() {
    this.currentStep++;
    if (this.currentStep >= this.STEPS.length) {
      this.finish();
      return;
    }
    this._render();
  }

  finish() {
    this.active = false;
    if (this.overlay) this.overlay.style.display = 'none';
    localStorage.setItem('signal_city_tutorial_done', 'true');
    this.game?.showToast('Tutorial complete! Go build your city.', 'success');
  }

  _render() {
    const step = this.STEPS[this.currentStep];
    if (!step) return;

    if (this.titleEl) this.titleEl.textContent = step.title;
    if (this.bodyEl) this.bodyEl.textContent = step.body;

    // Dots
    if (this.dotsEl) {
      this.dotsEl.innerHTML = this.STEPS.map((_, i) =>
        `<div style="width:6px;height:6px;border-radius:50%;background:${i === this.currentStep ? '#1D9E75' : 'rgba(255,255,255,0.2)'}"></div>`
      ).join('');
    }

    // Position card near target
    if (step.target && this.card) {
      const el = document.querySelector(step.target);
      if (el) {
        const rect = el.getBoundingClientRect();
        this.card.style.top = `${rect.bottom + 10}px`;
        this.card.style.left = `${Math.min(rect.left, window.innerWidth - 340)}px`;
        this.card.style.transform = 'none';
      } else {
        this.card.style.top = '50%';
        this.card.style.left = '50%';
        this.card.style.transform = 'translate(-50%, -50%)';
      }
    } else if (this.card) {
      this.card.style.top = '50%';
      this.card.style.left = '50%';
      this.card.style.transform = 'translate(-50%, -50%)';
    }
  }
}

// Global handlers
window.nextTutorialStep = function() { window.game?.tutorial?.next(); };
window.skipTutorial = function() { window.game?.tutorial?.finish(); };
