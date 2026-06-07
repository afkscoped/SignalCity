// static/js/city.js — Three.js 3D city builder and manager

export class CityBuilder {
  constructor(scene) {
    this.scene = scene;
    this.nodeObjects = new Map();    // node_id → THREE.Mesh
    this.edgeObjects = new Map();    // "u-v" → {mesh, line, state, targetColor}
    this.buildingObjects = [];
    this.groundMesh = null;
    this.labelSprites = [];
    this.graph = null;
    this._time = 0;
    this._colorTransitions = [];
    this._particles = [];

    // State colors
    this.EDGE_COLORS = {
      unvisited:  new THREE.Color(0x2D3748),
      frontier:   new THREE.Color(0xEF9F27),
      added:      new THREE.Color(0x1D9E75),
      relaxed:    new THREE.Color(0x378ADD),
      flow:       new THREE.Color(0x1D9E75),
      bottleneck: new THREE.Color(0xE24B4A),
      path:       new THREE.Color(0xF59E0B),
      community:  new THREE.Color(0x8B5CF6),
      facility:   new THREE.Color(0xF59E0B),
      weather:    new THREE.Color(0xE24B4A),
    };

    this.NODE_COLORS = {
      default:   new THREE.Color(0x1D3D33),
      frontier:  new THREE.Color(0xEF9F27),
      visited:   new THREE.Color(0x1D9E75),
      source:    new THREE.Color(0x22c787),
      sink:      new THREE.Color(0xE24B4A),
      path:      new THREE.Color(0xF59E0B),
      facility:  new THREE.Color(0xF59E0B),
      hub:       new THREE.Color(0x8B5CF6),
    };
  }

  buildCity(graphData) {
    this.clear();
    this.graph = graphData;
    const nodes = graphData.nodes || [];
    const edges = graphData.edges || [];

    // Ground plane
    const groundGeo = new THREE.PlaneGeometry(300, 300, 30, 30);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x0D1F1A,
      roughness: 0.9,
      metalness: 0.1,
    });
    this.groundMesh = new THREE.Mesh(groundGeo, groundMat);
    this.groundMesh.rotation.x = -Math.PI / 2;
    this.groundMesh.position.y = -0.5;
    this.groundMesh.receiveShadow = true;
    this.scene.add(this.groundMesh);

    // Grid lines
    const gridHelper = new THREE.GridHelper(300, 30, 0x1D3D33, 0x0F1A15);
    gridHelper.position.y = -0.4;
    this.scene.add(gridHelper);
    this._gridHelper = gridHelper;

    // Build nodes
    const nodeSphereGeo = new THREE.SphereGeometry(0.7, 10, 10);
    const nodeMap = new Map();
    for (const node of nodes) {
      nodeMap.set(node.id, node);
      const pop = node.pop_weight || 1.0;
      const color = new THREE.Color().lerpColors(
        new THREE.Color(0x1D3D33),
        new THREE.Color(0x1D9E75),
        Math.min(pop / 3.0, 1.0)
      );
      const mat = new THREE.MeshStandardMaterial({
        color, emissive: color, emissiveIntensity: 0.1,
        roughness: 0.5, metalness: 0.3,
      });
      const mesh = new THREE.Mesh(nodeSphereGeo, mat);
      mesh.position.set(node.x, 0.7, node.y);
      mesh.userData = { nodeId: node.id, baseColor: color.clone(), targetScale: 1.0 };
      mesh.castShadow = true;
      this.scene.add(mesh);
      this.nodeObjects.set(node.id, mesh);
    }

    // Build edges as lines (much faster than TubeGeometry for large graphs)
    const edgeMat = new THREE.LineBasicMaterial({ color: 0x2D3748, transparent: true, opacity: 0.5 });
    for (const edge of edges) {
      const u = nodeMap.get(edge.u);
      const v = nodeMap.get(edge.v);
      if (!u || !v) continue;

      const points = [];
      const midY = 0.5 + Math.sqrt((u.x - v.x) ** 2 + (u.y - v.y) ** 2) / 40;
      points.push(new THREE.Vector3(u.x, 0.7, u.y));
      points.push(new THREE.Vector3((u.x + v.x) / 2, midY, (u.y + v.y) / 2));
      points.push(new THREE.Vector3(v.x, 0.7, v.y));

      const curve = new THREE.QuadraticBezierCurve3(points[0], points[1], points[2]);
      const geo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(12));
      const mat2 = edgeMat.clone();
      const line = new THREE.Line(geo, mat2);
      this.scene.add(line);

      const key = `${Math.min(edge.u, edge.v)}-${Math.max(edge.u, edge.v)}`;
      this.edgeObjects.set(key, {
        line, state: 'unvisited',
        targetColor: this.EDGE_COLORS.unvisited.clone(),
        currentColor: this.EDGE_COLORS.unvisited.clone(),
      });
    }

    // Buildings at high-pop nodes
    const boxGeo = new THREE.BoxGeometry(1, 1, 1);
    for (const node of nodes) {
      if (node.pop_weight > 1.8) {
        const height = node.pop_weight * 2 + Math.random() * 3;
        const buildMat = new THREE.MeshStandardMaterial({
          color: 0x0F2D1F,
          emissive: 0x1D9E75,
          emissiveIntensity: 0.03,
          roughness: 0.7,
          metalness: 0.4,
        });
        const building = new THREE.Mesh(boxGeo, buildMat);
        building.scale.set(1.5 + Math.random(), height, 1.5 + Math.random());
        building.position.set(node.x + 1.5, height / 2, node.y + 1.5);
        building.castShadow = true;
        this.scene.add(building);
        this.buildingObjects.push(building);
      }
    }

    // City name label
    this._createLabel(graphData.city_name || 'Signal City', 0, 15, 0);
  }

  setEdgeState(u, v, state) {
    const key = `${Math.min(u, v)}-${Math.max(u, v)}`;
    const edgeObj = this.edgeObjects.get(key);
    if (!edgeObj) return;

    edgeObj.state = state;
    const targetColor = this.EDGE_COLORS[state] || this.EDGE_COLORS.unvisited;
    edgeObj.targetColor = targetColor.clone();

    // Immediate color + opacity update
    edgeObj.line.material.color.copy(targetColor);
    edgeObj.line.material.opacity = state === 'unvisited' ? 0.3 : 0.9;

    if (state === 'bottleneck') {
      edgeObj.line.material.opacity = 1.0;
    }
  }

  setNodeState(nodeId, state) {
    const mesh = this.nodeObjects.get(nodeId);
    if (!mesh) return;

    const color = this.NODE_COLORS[state] || this.NODE_COLORS.default;
    mesh.material.color.copy(color);
    mesh.material.emissive.copy(color);

    switch (state) {
      case 'frontier':
        mesh.material.emissiveIntensity = 0.4;
        mesh.userData.targetScale = 1.4;
        break;
      case 'visited':
        mesh.material.emissiveIntensity = 0.2;
        mesh.userData.targetScale = 1.1;
        break;
      case 'source':
      case 'sink':
      case 'facility':
        mesh.material.emissiveIntensity = 0.5;
        mesh.userData.targetScale = 2.0;
        break;
      case 'path':
      case 'hub':
        mesh.material.emissiveIntensity = 0.4;
        mesh.userData.targetScale = 1.6;
        break;
      default:
        mesh.material.emissiveIntensity = 0.1;
        mesh.userData.targetScale = 1.0;
    }
  }

  setCommunityColors(communities) {
    if (!communities) return;
    const palette = [0x1D9E75, 0x378ADD, 0x8B5CF6, 0xEF9F27, 0xE24B4A, 0xF59E0B, 0x06B6D4, 0xEC4899];
    for (const [nodeIdStr, commId] of Object.entries(communities)) {
      const nodeId = parseInt(nodeIdStr);
      const mesh = this.nodeObjects.get(nodeId);
      if (mesh) {
        const color = new THREE.Color(palette[commId % palette.length]);
        mesh.material.color.copy(color);
        mesh.material.emissive.copy(color);
        mesh.material.emissiveIntensity = 0.3;
      }
    }
  }

  setFacilityMarker(nodeId, type) {
    const mesh = this.nodeObjects.get(nodeId);
    if (!mesh) return;
    this.setNodeState(nodeId, 'facility');
    // Add a ring around facility
    const ringGeo = new THREE.RingGeometry(2, 2.5, 32);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0xF59E0B, side: THREE.DoubleSide, transparent: true, opacity: 0.4 });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.copy(mesh.position);
    ring.position.y = 0.1;
    this.scene.add(ring);
    this.buildingObjects.push(ring);
  }

  spawnParticles(type, x, y, z, count = 15) {
    const positions = [];
    const velocities = [];
    const lifetimes = [];

    for (let i = 0; i < count; i++) {
      positions.push(x + (Math.random() - 0.5) * 2, y + Math.random() * 2, z + (Math.random() - 0.5) * 2);
      velocities.push((Math.random() - 0.5) * 3, Math.random() * 4 + 1, (Math.random() - 0.5) * 3);
      lifetimes.push(Math.random() * 0.5 + 0.3);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

    const colors = { build: 0x1D9E75, flow: 0xEF9F27, settle: 0x378ADD, weather_storm: 0xE24B4A, weather_rain: 0x378ADD };
    const mat = new THREE.PointsMaterial({
      color: colors[type] || 0x1D9E75,
      size: 0.5, transparent: true, opacity: 0.8,
    });

    const points = new THREE.Points(geo, mat);
    this.scene.add(points);
    this._particles.push({
      mesh: points, velocities, lifetimes,
      startTime: performance.now() / 1000,
      maxLife: 0.8,
    });
  }

  resetStates() {
    for (const [_, edgeObj] of this.edgeObjects) {
      edgeObj.state = 'unvisited';
      edgeObj.line.material.color.copy(this.EDGE_COLORS.unvisited);
      edgeObj.line.material.opacity = 0.3;
    }
    for (const [_, mesh] of this.nodeObjects) {
      mesh.material.color.copy(mesh.userData.baseColor);
      mesh.material.emissive.copy(mesh.userData.baseColor);
      mesh.material.emissiveIntensity = 0.1;
      mesh.userData.targetScale = 1.0;
      mesh.scale.setScalar(1.0);
    }
  }

  applyWeatherEffect(weatherEvent) {
    if (!weatherEvent || weatherEvent.type === 'CLEAR') return;
    const color = new THREE.Color(weatherEvent.color || '#E24B4A');

    // Tint fog
    if (weatherEvent.type === 'FOG') {
      this.scene.fog = new THREE.FogExp2(0x888780, 0.015);
    } else if (weatherEvent.type === 'STORM' || weatherEvent.type === 'BLIZZARD') {
      this.scene.fog = new THREE.FogExp2(0x0A0E14, 0.012);
    }

    // Spawn weather particles at random positions
    for (let i = 0; i < 5; i++) {
      const x = (Math.random() - 0.5) * 100;
      const z = (Math.random() - 0.5) * 100;
      this.spawnParticles('weather_storm', x, 5, z, 10);
    }
  }

  update(time) {
    this._time = time;

    // Animate node scales
    for (const [_, mesh] of this.nodeObjects) {
      const target = mesh.userData.targetScale || 1.0;
      const current = mesh.scale.x;
      if (Math.abs(current - target) > 0.01) {
        const newScale = current + (target - current) * 0.1;
        mesh.scale.setScalar(newScale);
      }
    }

    // Pulse bottleneck edges
    for (const [_, edgeObj] of this.edgeObjects) {
      if (edgeObj.state === 'bottleneck') {
        const pulse = 0.5 + 0.5 * Math.sin(time * 6);
        edgeObj.line.material.opacity = 0.5 + pulse * 0.5;
      }
    }

    // Update particles
    const now = performance.now() / 1000;
    for (let i = this._particles.length - 1; i >= 0; i--) {
      const p = this._particles[i];
      const age = now - p.startTime;
      if (age > p.maxLife) {
        this.scene.remove(p.mesh);
        p.mesh.geometry.dispose();
        p.mesh.material.dispose();
        this._particles.splice(i, 1);
        continue;
      }
      p.mesh.material.opacity = Math.max(0, 0.8 * (1 - age / p.maxLife));

      // Move particles upward
      const pos = p.mesh.geometry.attributes.position;
      for (let j = 0; j < pos.count; j++) {
        pos.setY(j, pos.getY(j) + 0.05);
      }
      pos.needsUpdate = true;
    }
  }

  clear() {
    // Remove all city objects
    for (const [_, mesh] of this.nodeObjects) {
      this.scene.remove(mesh);
      mesh.geometry?.dispose();
      mesh.material?.dispose();
    }
    this.nodeObjects.clear();

    for (const [_, obj] of this.edgeObjects) {
      this.scene.remove(obj.line);
      obj.line.geometry?.dispose();
      obj.line.material?.dispose();
    }
    this.edgeObjects.clear();

    for (const b of this.buildingObjects) {
      this.scene.remove(b);
      b.geometry?.dispose();
      b.material?.dispose();
    }
    this.buildingObjects = [];

    if (this.groundMesh) { this.scene.remove(this.groundMesh); this.groundMesh = null; }
    if (this._gridHelper) { this.scene.remove(this._gridHelper); this._gridHelper = null; }

    for (const s of this.labelSprites) { this.scene.remove(s); }
    this.labelSprites = [];

    for (const p of this._particles) {
      this.scene.remove(p.mesh);
      p.mesh.geometry?.dispose();
      p.mesh.material?.dispose();
    }
    this._particles = [];
  }

  _createLabel(text, x, y, z) {
    const canvas = document.createElement('canvas');
    canvas.width = 512; canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = 'rgba(0,0,0,0)';
    ctx.fillRect(0, 0, 512, 64);
    ctx.fillStyle = '#1D9E75';
    ctx.font = 'bold 28px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(text, 256, 40);

    const texture = new THREE.CanvasTexture(canvas);
    const mat = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(mat);
    sprite.position.set(x, y, z);
    sprite.scale.set(30, 4, 1);
    this.scene.add(sprite);
    this.labelSprites.push(sprite);
  }

  getNodePosition(nodeId) {
    const mesh = this.nodeObjects.get(nodeId);
    if (mesh) return mesh.position;
    return null;
  }
}
