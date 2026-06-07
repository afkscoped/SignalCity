// static/js/main.js — Scene setup, game orchestration, and module coordination
import { CityBuilder } from './city.js';
import { AlgorithmRunner } from './algorithms.js';
import { HUD } from './hud.js';
import { Tutorial } from './tutorial.js';
import { XAI } from './xai.js';
import { Analytics } from './analytics.js';

const ALGO_META = {
  prim:         { name: "Prim's MST",              icon: '⚡', tier: 1, cost: 5,  category: 'mst',         color: '#1D9E75' },
  kruskal:      { name: "Kruskal's MST",           icon: '🌲', tier: 2, cost: 8,  category: 'mst',         color: '#1D9E75' },
  dijkstra:     { name: "Dijkstra",                icon: '🛤️', tier: 2, cost: 8,  category: 'pathfinding', color: '#378ADD' },
  edmonds_karp: { name: "Max Flow",                icon: '🌊', tier: 3, cost: 15, category: 'flow',        color: '#378ADD' },
  edf:          { name: "EDF Schedule",            icon: '⏰', tier: 1, cost: 5,  category: 'scheduling',  color: '#EF9F27' },
  sjf:          { name: "SJF Schedule",            icon: '📋', tier: 2, cost: 8,  category: 'scheduling',  color: '#EF9F27' },
  fcfs:         { name: "FCFS",                    icon: '📝', tier: 1, cost: 3,  category: 'scheduling',  color: '#6B7280' },
  rr:           { name: "Round Robin",             icon: '🔄', tier: 2, cost: 6,  category: 'scheduling',  color: '#EF9F27' },
  leiden:       { name: "Leiden Districts",        icon: '🏘️', tier: 4, cost: 20, category: 'analysis',    color: '#8B5CF6' },
  pagerank:     { name: "PageRank",                icon: '📊', tier: 4, cost: 18, category: 'analysis',    color: '#8B5CF6' },
  contraction:  { name: "Contraction Hierarchies", icon: '🚀', tier: 5, cost: 25, category: 'pathfinding', color: '#F59E0B' },
  k_median:     { name: "k-Median Facility",       icon: '🏥', tier: 5, cost: 25, category: 'optimization',color: '#F59E0B' },

  # Metaheuristics (Facility Placement)
  gwo:          { name: "Grey Wolf (GWO)",         icon: '🐺', tier: 3, cost: 12, category: 'optimization',color: '#EF9F27' },
  alo:          { name: "Ant Lion (ALO)",          icon: '🐜', tier: 3, cost: 12, category: 'optimization',color: '#EF9F27' },
  hho:          { name: "Harris Hawks (HHO)",      icon: '🦅', tier: 4, cost: 15, category: 'optimization',color: '#EF9F27' },
  coa:          { name: "Coati Opt (COA)",         icon: '🦝', tier: 5, cost: 20, category: 'optimization',color: '#EF9F27' },

  # Metaheuristics (Traffic & Signal)
  woa:          { name: "Whale Opt (WOA)",         icon: '🐋', tier: 3, cost: 12, category: 'optimization',color: '#378ADD' },
  run:          { name: "Runge-Kutta (RUN)",       icon: '📈', tier: 4, cost: 16, category: 'optimization',color: '#378ADD' },
  ptbo:         { name: "Painting Opt (PTBO)",     icon: '🎨', tier: 5, cost: 22, category: 'optimization',color: '#378ADD' },
  mpa:          { name: "Marine Pred (MPA)",       icon: '🦈', tier: 4, cost: 15, category: 'optimization',color: '#378ADD' },

  # Metaheuristics (Signal Coverage)
  mfo:          { name: "Moth-Flame (MFO)",        icon: '🦋', tier: 3, cost: 10, category: 'optimization',color: '#F59E0B' },
  goa:          { name: "Grasshopper (GOA)",       icon: '🦗', tier: 4, cost: 14, category: 'optimization',color: '#F59E0B' },
  ao:           { name: "Aquila Opt (AO)",         icon: '🦤', tier: 4, cost: 15, category: 'optimization',color: '#F59E0B' },
  do:           { name: "Dandelion (DO)",          icon: '🌾', tier: 5, cost: 18, category: 'optimization',color: '#F59E0B' },

  # Metaheuristics (Utility Balancing)
  ssa:          { name: "Salp Swarm (SSA)",        icon: '🧬', tier: 3, cost: 12, category: 'optimization',color: '#8B5CF6' },
  sma:          { name: "Slime Mould (SMA)",       icon: '🦠', tier: 4, cost: 16, category: 'optimization',color: '#8B5CF6' },
  aoa:          { name: "Arithmetic (AOA)",        icon: '🧮', tier: 3, cost: 10, category: 'optimization',color: '#8B5CF6' },
  gto:          { name: "Gorilla Troops (GTO)",    icon: '🦍', tier: 5, cost: 20, category: 'optimization',color: '#8B5CF6' },

  # Machine Learning / AI
  transformer:  { name: "Transformer",             icon: '🤖', tier: 3, cost: 18, category: 'ml',           color: '#8B5CF6' },
  kan:          { name: "KAN Congestion",          icon: '🕸', tier: 5, cost: 25, category: 'ml',           color: '#8B5CF6' },
  vit:          { name: "Swin Zoning",             icon: '🔲', tier: 4, cost: 20, category: 'ml',           color: '#8B5CF6' },
  diffusion:    { name: "Diffusion Density",       icon: '🌫', tier: 5, cost: 24, category: 'ml',           color: '#8B5CF6' },

  # Systems
  raft:         { name: "Raft Consensus",          icon: '⛵', tier: 3, cost: 15, category: 'systems',      color: '#E24B4A' },
  xgboost:      { name: "XGBoost Split",           icon: '🌳', tier: 4, cost: 18, category: 'systems',      color: '#E24B4A' },
  count_sketch: { name: "Count Sketch Stream",     icon: '✏️', tier: 3, cost: 10, category: 'systems',      color: '#E24B4A' },
  learned_index:{ name: "Learned Index (RMI)",     icon: '📖', tier: 4, cost: 16, category: 'systems',      color: '#E24B4A' },
};

class SignalCity {
  constructor() {
    this.ALGO_META = ALGO_META;
    // Three.js scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x080A0D);
    this.scene.fog = new THREE.FogExp2(0x080A0D, 0.006);

    // Camera
    this.camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 1000);
    this.camera.position.set(0, 100, 80);
    this.camera.lookAt(0, 0, 0);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({
      canvas: document.getElementById('gameCanvas'),
      antialias: true, alpha: false,
    });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // Lighting
    const ambient = new THREE.AmbientLight(0x334155, 0.65);
    this.scene.add(ambient);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(50, 120, 50);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    this.scene.add(dirLight);

    const pointLight = new THREE.PointLight(0xc5a059, 0.6, 200);
    pointLight.position.set(0, 30, 0);
    this.scene.add(pointLight);

    // Raycaster
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    // Orbit controls
    this._orbitState = { dragging: false, button: -1, lastX: 0, lastY: 0, theta: 0, phi: Math.PI / 4, distance: 130 };

    // Modules
    this.cityBuilder = new CityBuilder(this.scene);
    this.algoRunner = new AlgorithmRunner(this.scene);
    this.hud = new HUD();
    this.tutorial = new Tutorial(this);
    this.xai = new XAI();
    this.analytics = new Analytics();

    // State
    this.currentCity = null;
    this.currentCityId = null;
    this.isRunning = false;
    this.speed = 1.0;
    this.profile = null;
    this.quests = [];
    this.cities = [];

    this._bindEvents();
    this._startRenderLoop();
    this._init();
  }

  async _init() {
    // Check for saved profile
    const saved = localStorage.getItem('signal_city_profile');
    if (saved) {
      try {
        this.profile = JSON.parse(saved);
        if (this.profile.id !== 'guest') {
          // Sync with DB
          try {
            const res = await fetch(`/api/profile/${this.profile.id}`);
            if (res.ok) {
              this.profile = await res.json();
              localStorage.setItem('signal_city_profile', JSON.stringify(this.profile));
            }
          } catch (e) {}
        }
        this._updateProfileUI();
        this.hud.updateResources(this.profile);
      } catch (e) {}
    }

    // Fetch cities
    try {
      const res = await fetch('/api/cities');
      this.cities = await res.json();
      this._populateCityDropdown();
    } catch (e) {
      console.error('Failed to fetch cities:', e);
    }

    // Fetch quests
    try {
      const res = await fetch('/api/quests');
      this.quests = await res.json();
    } catch (e) {}

    // Populate algorithm buttons
    this._populateAlgoButtons();

    // Skip landing if logged in
    if (saved && this.profile) {
      document.getElementById('landingPage').style.display = 'none';
      if (typeof showHomePage === 'function') showHomePage();
    }
  }

  setProfile(profile) {
    this.profile = profile;
    localStorage.setItem('signal_city_profile', JSON.stringify(profile));
    this._updateProfileUI();
    this.hud.updateResources(profile);
  }

  _updateProfileUI() {
    if (!this.profile) return;
    const p = this.profile;
    const setT = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };

    setT('profileName', p.username || 'Guest');
    setT('profileLevel', `Lv.${p.level || 1}`);
    setT('profileCoins', `🪙 ${p.coins || 0}`);
    setT('profileAvatar', p.avatar || '🧙');

    // Top yields updates
    setT('topTurn', p.current_turn || 0);
    setT('topCredits', p.research_points || 0);
    setT('topCoins', p.coins || 0);
    setT('topRP', p.research_points || 0);
    setT('topPop', p.population || 100);
    setT('topHappy', `${p.happiness || 50}%`);
  }

  updateHomePage() {
    if (!this.profile) return;
    const p = this.profile;
    const setT = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };

    setT('homeUsername', p.username || 'Architect');
    setT('homeClass', p.character_class || 'Algorithm Mage');
    setT('homeAvatar', p.avatar || '🧙');
    setT('homeLevel', p.level || 1);
    setT('homeCoins', p.coins || 0);
    setT('homeRP', p.research_points || 0);
    setT('homeHappiness', p.happiness || 50);
    setT('homePop', p.population || 100);
    setT('homeTurn', p.current_turn || 0);

    // XP bar
    const xpNeeded = p.xp_to_next || 100;
    const xpCurrent = p.xp || 0;
    const xpPct = Math.min(100, Math.round(xpCurrent / xpNeeded * 100));
    setT('homeXP', `${xpCurrent} / ${xpNeeded} XP`);
    const xpBar = document.getElementById('homeXPBar');
    if (xpBar) xpBar.style.width = `${xpPct}%`;

    // Quests & Tech Tree
    this._renderQuestList('questList');
    this._renderTechTree();
  }

  _renderQuestList(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const unlocked = this.profile?.unlocked_algos || ['prim', 'fcfs'];
    const completed = this.profile?.completed_quests || [];

    container.innerHTML = this.quests.map(q => {
      const done = completed.includes(q.id);
      const locked = !unlocked.includes(q.algorithm) && q.algorithm !== 'prim';
      return `
        <div class="quest-card ${done ? 'completed' : ''}" onclick="${done || locked ? '' : `acceptQuest('${q.id}','${q.algorithm}')`}">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-civ font-bold ${done ? 'text-green-400' : 'text-gray-300'}">${done ? '✅ ' : ''}${q.title}</span>
            <span class="badge badge-${q.difficulty}">${q.difficulty}</span>
          </div>
          <p class="text-[11px] text-gray-500 mb-2 leading-tight">${q.description}</p>
          <div class="flex items-center gap-3 text-[10px] font-mono">
            <span class="text-purple-400">+${q.reward_xp} XP</span>
            <span class="text-yellow-500">+${q.reward_coins} 🪙</span>
            ${locked ? '<span class="text-red-400 font-civ">🔒 LOCKED</span>' : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  _renderTechTree() {
    const container = document.getElementById('techTree');
    if (!container) return;
    const unlocked = this.profile?.unlocked_algos || ['prim', 'fcfs'];

    const tiers = [1, 2, 3, 4, 5];
    let html = '';
    for (const tier of tiers) {
      const algos = Object.entries(ALGO_META).filter(([_, m]) => m.tier === tier);
      html += `<div class="mb-3"><div class="flex items-center gap-1 mb-1"><span class="tier text-[9px] font-civ font-bold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">TIER ${tier}</span></div>`;
      for (const [key, meta] of algos) {
        const isUnlocked = unlocked.includes(key);
        html += `
          <div class="flex items-center gap-2 py-1 px-2 rounded ${isUnlocked ? 'bg-white/[0.03]' : 'opacity-60'}">
            <span class="text-xs">${meta.icon}</span>
            <span class="text-[10px] font-civ ${isUnlocked ? 'text-gray-300' : 'text-gray-400'}">${meta.name}</span>
            ${!isUnlocked ? `<span class="text-[9px] text-yellow-500/90 hover:text-yellow-300 ml-auto font-mono cursor-pointer bg-yellow-500/5 border border-yellow-500/20 px-1 py-0.5 rounded transition" onclick="window.game.unlockAlgorithm('${key}')" title="Unlock for ${meta.cost} Research Points">🔒 ${meta.cost} RP</span>` : '<span class="text-[9px] text-green-500 ml-auto font-bold font-civ">✓</span>'}
          </div>
        `;
      }
      html += '</div>';
    }
    container.innerHTML = html;
  }

  async unlockAlgorithm(algoKey) {
    if (!this.profile) {
      this.showToast('Please log in to unlock algorithms.', 'error');
      return;
    }
    const meta = ALGO_META[algoKey];
    if (!meta) return;

    if (this.profile.unlocked_algos.includes(algoKey)) {
      this.showToast('Algorithm already unlocked.', 'info');
      return;
    }

    const cost = meta.cost || 0;
    if (this.profile.research_points < cost) {
      this.showToast(`Requires ${cost} RP (you have ${this.profile.research_points} RP). End turn to generate more research!`, 'error');
      return;
    }

    try {
      if (this.profile.id === 'guest') {
        this.profile.research_points -= cost;
        this.profile.unlocked_algos.push(algoKey);
        localStorage.setItem('signal_city_profile', JSON.stringify(this.profile));
        this.showToast(`Unlocked ${meta.name}!`, 'success');
        this.updateHomePage();
        this._updateProfileUI();
        this._populateAlgoButtons();
      } else {
        const res = await fetch(`/api/profile/${this.profile.id}/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            research_points: -cost,
            unlock_algo: algoKey
          })
        });
        if (res.ok) {
          const updated = await res.json();
          this.setProfile(updated);
          this.showToast(`Unlocked ${meta.name}!`, 'success');
          this.updateHomePage();
          this._populateAlgoButtons();
        } else {
          const errData = await res.json();
          this.showToast(errData.error || 'Failed to unlock algorithm.', 'error');
        }
      }
    } catch (e) {
      console.error(e);
      this.showToast('Error communicating with server.', 'error');
    }
  }

  populateQuestModal() {
    this._renderQuestList('questModalList');
  }

  _populateCityDropdown() {
    const dd = document.getElementById('cityDropdown');
    if (!dd) return;
    dd.innerHTML = '<option value="">Select City...</option>';
    for (const city of this.cities) {
      dd.innerHTML += `<option value="${city.id}">${city.name}</option>`;
    }
  }

  _populateAlgoButtons() {
    const container = document.getElementById('algoButtons');
    if (!container) return;
    const unlocked = this.profile?.unlocked_algos || ['prim', 'fcfs'];

    container.innerHTML = Object.entries(ALGO_META).map(([key, meta]) => {
      const isLocked = !unlocked.includes(key);
      return `<button id="btn-${key}" class="btn-algo text-[10px] ${isLocked ? 'locked' : ''}"
                onclick="window.game.runAlgorithm('${key}')"
                ${isLocked ? 'disabled' : ''}
                title="${meta.name} (Tier ${meta.tier}, ${meta.cost} credits)">
                ${meta.icon} ${meta.name}
              </button>`;
    }).join('');
  }

  async loadCity(cityId, cityName = null) {
    if (!cityId) return;
    this.currentCityId = cityId;

    // Show loading
    document.getElementById('loadingScreen').style.display = 'flex';
    this._setLoading('Downloading street grids...', 20);

    try {
      const res = await fetch('/api/load-city', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city_id: cityId, city_name: cityName }),
      });
      const data = await res.json();

      if (data.status !== 'ok') {
        this.showToast('Failed to geocode city: ' + (data.message || 'Unknown error'), 'error');
        document.getElementById('loadingScreen').style.display = 'none';
        return;
      }

      this._setLoading('Building 3D road layouts...', 60);
      this.currentCity = data.graph;
      this.cityBuilder.buildCity(data.graph);
      this.algoRunner.setGraph(data.graph);

      this._setLoading('Checking local weather...', 80);

      // Fetch weather
      try {
        const centroid = data.graph.centroid || {};
        const wRes = await fetch(`/api/weather/${centroid.lat || 0}/${centroid.lon || 0}`);
        const weather = await wRes.json();
        this._applyWeather(weather);
      } catch (e) {}

      this._setLoading('Grid Complete!', 100);
      this.hud.reset();
      this.xai.reset();
      
      const sourceLabel = data.graph.metadata?.source === 'overpass' ? 'OpenStreetMap live' : 'Offline fallback';
      this.showToast(`Loaded ${data.graph.city_name} (${data.graph.node_count} intersections, ${data.graph.edge_count} roads) via ${sourceLabel}`, 'success');

      // Update dropdown
      if (!this.cities.find(c => c.id === cityId)) {
        this.cities.push({ id: cityId, name: data.graph.city_name });
        this._populateCityDropdown();
      }
      
      const dd = document.getElementById('cityDropdown');
      if (dd) dd.value = cityId;

      setTimeout(() => {
        document.getElementById('loadingScreen').style.display = 'none';
      }, 500);

      if (!localStorage.getItem('signal_city_tutorial_done')) {
        setTimeout(() => this.tutorial.start(), 1000);
      }

    } catch (e) {
      this.showToast('Error mapping coordinates: ' + e.message, 'error');
      document.getElementById('loadingScreen').style.display = 'none';
    }
  }

  _applyWeather(weather) {
    if (!weather) return;
    const banner = document.getElementById('weatherBanner');
    if (banner) {
      document.getElementById('weatherIcon').textContent = weather.icon || '☀️';
      document.getElementById('weatherText').textContent = (weather.description || 'Clear').toUpperCase();
      document.getElementById('weatherLore').textContent = weather.lore || '';
      banner.style.display = 'block';
      banner.style.borderColor = weather.color || '#c5a059';
    }
    
    // Apply visual effects
    this.cityBuilder.applyWeatherEffect(weather);
    const topWeather = document.getElementById('topWeather');
    if (topWeather) {
      topWeather.textContent = `${weather.icon || '☀️'} ${(weather.type || 'CLEAR')}`;
      topWeather.style.color = weather.color || '#fff';
    }
  }

  async runAlgorithm(algoName, params = {}) {
    if (this.isRunning) {
      this.showToast('Algorithm already running. Please wait.', 'info');
      return;
    }
    
    // Procedural generation does not need existing city
    if (!this.currentCity && algoName !== 'procedural_generation') {
      this.showToast('Load a city map first!', 'info');
      return;
    }

    const meta = ALGO_META[algoName];
    if (!meta) return;

    // Check if unlocked
    const unlocked = this.profile?.unlocked_algos || ['prim', 'fcfs'];
    if (!unlocked.includes(algoName) && algoName !== 'procedural_generation') {
      this.showToast(`${meta.name} is locked! Unlock it with Research Points in the Codex.`, 'error');
      return;
    }

    this.isRunning = true;
    this.hud.startAlgo(meta.name);
    this.xai.reset();
    this.xai.setEstimate(this.currentCity?.node_count || 100);
    this.analytics.startRun(algoName, this.currentCityId);

    // Show/hide panels based on category
    const isScheduling = meta.category === 'scheduling';
    const isFlow = meta.category === 'flow';
    document.getElementById('ganttPanel').style.display = isScheduling ? 'block' : 'none';
    document.getElementById('flowPanel').style.display = isFlow ? 'block' : 'none';

    // Highlight active button
    document.querySelectorAll('#algoButtons button').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`btn-${algoName}`);
    if (btn) btn.classList.add('active');

    try {
      await this.algoRunner.run(algoName, {
        speed_ms: Math.round(120 / this.speed),
        cityId: this.currentCityId,
        params: params,
        onStep: (delta, stats) => {
          this.hud.update(stats);
          this.xai.update(delta.xai_text, stats);
          this.analytics.recordStep(delta);
          
          // Handle procedural generation steps
          if (algoName === 'procedural_generation') {
            if (delta.kind === 'terrain_generated') {
              this.cityBuilder.clear();
              this.cityBuilder.buildCity({ nodes: delta.nodes, edges: [] });
            } else if (delta.kind === 'hubs_placed') {
              this.cityBuilder.clear();
              this.cityBuilder.buildCity({ nodes: delta.nodes, edges: [] });
              for (const hub of delta.hubs) {
                this.cityBuilder.setFacilityMarker(hub.id, 'hospital');
              }
            } else if (delta.kind === 'mst_generated') {
              this.cityBuilder.clear();
              this.cityBuilder.buildCity({ nodes: this.cityBuilder.graph.nodes, edges: delta.edges });
              for (const e of delta.edges) {
                this.cityBuilder.setEdgeState(e.u, e.v, 'added');
              }
            }
          }

          if (['job_start', 'job_complete', 'job_preempt'].includes(delta.kind)) this.hud.updateGantt(delta);
          if (delta.kind === 'augmenting_path') this.hud.updateFlow(delta);
        },
        onComplete: (summary) => {
          this.hud.showSummary(summary);
          this.xai.showSummary(summary.xai_text || summary.xai_summary || 'Algorithm complete.');
          this.analytics.endRun(summary);
          this.isRunning = false;
          if (btn) btn.classList.remove('active');

          // If procedural generation completed, load the newly generated grid
          if (algoName === 'procedural_generation' && summary.graph) {
            this.currentCity = summary.graph;
            this.currentCityId = summary.graph.city_id;
            this.cityBuilder.buildCity(summary.graph);
            this.algoRunner.setGraph(summary.graph);
            
            if (!this.cities.find(c => c.id === this.currentCityId)) {
              this.cities.push({ id: this.currentCityId, name: summary.graph.city_name });
              this._populateCityDropdown();
            }
            const dd = document.getElementById('cityDropdown');
            if (dd) dd.value = this.currentCityId;
          }

          // Award rewards
          this._awardRewards(algoName, summary);
        },
      });
    } catch (e) {
      this.isRunning = false;
      if (btn) btn.classList.remove('active');
      console.error('Algorithm run failed:', e);
    }
  }

  async _awardRewards(algoName, summary) {
    if (!this.profile || this.profile.id === 'guest') {
      // Guest mode rewards
      this.profile.xp = (this.profile.xp || 0) + 50;
      this.profile.coins = (this.profile.coins || 0) + 25;
      const nextLevelXP = Math.round(100 * Math.pow(this.profile.level || 1, 1.5));
      if (this.profile.xp >= nextLevelXP) {
        this.profile.level = (this.profile.level || 1) + 1;
        this.showToast(`🎉 Level Up! You are now Level ${this.profile.level}!`, 'reward');
        this._unlockTierAlgos(this.profile.level);
      }
      this.profile.xp_to_next = Math.round(100 * Math.pow(this.profile.level, 1.5));
      localStorage.setItem('signal_city_profile', JSON.stringify(this.profile));
      this._updateProfileUI();
      this.showToast(`+50 XP, +25 🪙`, 'success');
      this._checkQuestCompletion(algoName);
      return;
    }

    // Server profile rewards
    try {
      const xpReward = 50 + Math.round((summary.op_count || 0) / 100);
      const coinReward = 25 + Math.round((summary.total_ops || summary.op_count || 0) / 200);
      const res = await fetch(`/api/profile/${this.profile.id}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ xp: xpReward, coins: coinReward, research_points: 12 }),
      });
      const updated = await res.json();
      if (updated.level > this.profile.level) {
        this.showToast(`🎉 Level Up! You are now Level ${updated.level}!`, 'reward');
        this._unlockTierAlgos(updated.level);
      }
      this.profile = updated;
      localStorage.setItem('signal_city_profile', JSON.stringify(updated));
      this._updateProfileUI();
      this.showToast(`+${xpReward} XP, +${coinReward} 🪙, +12 Research`, 'success');

      this._checkQuestCompletion(algoName);
    } catch (e) {
      console.error('Failed to update profile:', e);
    }
  }

  _unlockTierAlgos(level) {
    const tierUnlocks = { 2: ['kruskal', 'dijkstra', 'sjf', 'rr'], 4: ['edmonds_karp', 'edf'], 6: ['leiden', 'pagerank'], 8: ['contraction', 'k_median'] };
    for (const [lvl, algos] of Object.entries(tierUnlocks)) {
      if (level >= parseInt(lvl)) {
        for (const algo of algos) {
          if (!this.profile.unlocked_algos.includes(algo)) {
            this.profile.unlocked_algos.push(algo);
            this.showToast(`🔓 Unlocked: ${ALGO_META[algo]?.name || algo}!`, 'reward');
          }
        }
      }
    }
    localStorage.setItem('signal_city_profile', JSON.stringify(this.profile));
    this._populateAlgoButtons();
  }

  _checkQuestCompletion(algoName) {
    const completed = this.profile?.completed_quests || [];
    for (const quest of this.quests) {
      if (completed.includes(quest.id)) continue;
      if (quest.algorithm === algoName) {
        completed.push(quest.id);
        this.profile.completed_quests = completed;
        this.profile.xp = (this.profile.xp || 0) + quest.reward_xp;
        this.profile.coins = (this.profile.coins || 0) + quest.reward_coins;
        localStorage.setItem('signal_city_profile', JSON.stringify(this.profile));

        this._showReward(quest);

        if (this.profile.id !== 'guest') {
          fetch(`/api/profile/${this.profile.id}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ xp: quest.reward_xp, coins: quest.reward_coins, complete_quest: quest.id }),
          }).catch(() => {});
        }
        break;
      }
    }
  }

  _showReward(quest) {
    document.getElementById('rewardTitle').textContent = `Quest Complete: ${quest.title}`;
    document.getElementById('rewardDesc').textContent = quest.description;
    document.getElementById('rewardXP').textContent = `+${quest.reward_xp}`;
    document.getElementById('rewardGold').textContent = `+${quest.reward_coins}`;
    document.getElementById('rewardPopup').style.display = 'flex';
  }

  showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  _setLoading(text, pct) {
    const el = document.getElementById('loadingText');
    const bar = document.getElementById('loadingBar');
    if (el) el.textContent = text.toUpperCase();
    if (bar) bar.style.width = `${pct}%`;
  }

  _bindEvents() {
    window.addEventListener('resize', () => {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
    });

    const canvas = this.renderer.domElement;
    canvas.addEventListener('mousedown', (e) => {
      this._orbitState.dragging = true;
      this._orbitState.button = e.button;
      this._orbitState.lastX = e.clientX;
      this._orbitState.lastY = e.clientY;
    });

    window.addEventListener('mousemove', (e) => {
      if (!this._orbitState.dragging) return;
      const dx = e.clientX - this._orbitState.lastX;
      const dy = e.clientY - this._orbitState.lastY;
      this._orbitState.lastX = e.clientX;
      this._orbitState.lastY = e.clientY;

      if (this._orbitState.button === 0) {
        this._orbitState.theta -= dx * 0.005;
        this._orbitState.phi = Math.max(0.15, Math.min(1.4, this._orbitState.phi - dy * 0.005));
      } else if (this._orbitState.button === 2) {
        const panSpeed = this._orbitState.distance * 0.002;
        const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion);
        forward.y = 0; forward.normalize();
        const right = new THREE.Vector3(1, 0, 0).applyQuaternion(this.camera.quaternion);
        this.camera.position.add(right.multiplyScalar(-dx * panSpeed));
        this.camera.position.add(forward.multiplyScalar(dy * panSpeed));
      }
      this._updateCameraFromOrbit();
    });

    window.addEventListener('mouseup', () => { this._orbitState.dragging = false; });

    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      this._orbitState.distance = Math.max(30, Math.min(300, this._orbitState.distance + e.deltaY * 0.1));
      this._updateCameraFromOrbit();
    }, { passive: false });

    canvas.addEventListener('contextmenu', (e) => e.preventDefault());

    canvas.addEventListener('click', (e) => {
      const rect = canvas.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      this.raycaster.setFromCamera(this.mouse, this.camera);
      const intersects = this.raycaster.intersectObjects(
        Array.from(this.cityBuilder.nodeObjects.values())
      );

      if (intersects.length > 0) {
        const nodeId = intersects[0].object.userData.nodeId;
        if (nodeId !== undefined) {
          this.showToast(`Selected node ${nodeId}`, 'info');
          this.cityBuilder.setNodeState(nodeId, 'source');
        }
      }
    });
  }

  _updateCameraFromOrbit() {
    const o = this._orbitState;
    const target = new THREE.Vector3(0, 0, 0);
    this.camera.position.x = target.x + o.distance * Math.sin(o.phi) * Math.sin(o.theta);
    this.camera.position.y = target.y + o.distance * Math.cos(o.phi);
    this.camera.position.z = target.z + o.distance * Math.sin(o.phi) * Math.cos(o.theta);
    this.camera.lookAt(target);
  }

  _startRenderLoop() {
    const animate = () => {
      requestAnimationFrame(animate);
      const time = performance.now() / 1000;
      this.cityBuilder.update(time);
      this.renderer.render(this.scene, this.camera);
    };
    animate();
  }
}

window.acceptQuest = function(questId, algorithm) {
  if (window.game) {
    window.game.showToast(`Contract accepted! Execute ${algorithm} to fulfill.`, 'info');
    if (typeof enterGame === 'function') enterGame();
    if (!window.game.currentCity) window.game.loadCity('bangalore');
  }
};

window.game = new SignalCity();
