/**
 * RuView Observatory — Main Scene Orchestrator
 *
 * Room-based WiFi sensing visualization with:
 * - Pool of 4 human wireframe figures (multi-person scenarios)
 * - 7 pose types (standing, walking, lying, sitting, fallen, exercising, gesturing, crouching)
 * - Scenario-specific room props (chair, exercise mat, door, rubble wall, screen, desk)
 * - Dot-matrix mist body mass, particle trails, WiFi waves, signal field
 * - Reflective floor, settings dialog, and practical data HUD
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

import { DemoDataGenerator } from './demo-data.js';
import { NebulaBackground } from './nebula-background.js';
import { PostProcessing } from './post-processing.js';
import { FigurePool, SKELETON_PAIRS } from './figure-pool.js';
import { PoseSystem } from './pose-system.js';
import { ScenarioProps } from './scenario-props.js';
import { HudController, DEFAULTS, SETTINGS_VERSION, PRESETS, SCENARIO_NAMES } from './hud-controller.js';

// ---- Palette ----
const C = {
  greenGlow:  0x00d878,
  greenBright:0x3eff8a,
  greenDim:   0x0a6b3a,
  amber:      0xffb020,
  blueSignal: 0x2090ff,
  redAlert:   0xff3040,
  redHeart:   0xff4060,
  bgDeep:     0x080c14,
};

// SCENARIO_NAMES, DEFAULTS, SETTINGS_VERSION, PRESETS imported from hud-controller.js

// ---- Main Class ----

class Observatory {
  constructor() {
    this._canvas = document.getElementById('observatory-canvas');
    this.settings = { ...DEFAULTS };

    // Load saved settings
    try {
      const ver = localStorage.getItem('ruview-settings-version');
      if (ver === SETTINGS_VERSION) {
        const saved = localStorage.getItem('ruview-observatory-settings');
        if (saved) Object.assign(this.settings, JSON.parse(saved));
      } else {
        localStorage.removeItem('ruview-observatory-settings');
        localStorage.setItem('ruview-settings-version', SETTINGS_VERSION);
      }
    } catch {}

    // Renderer
    this._renderer = new THREE.WebGLRenderer({
      canvas: this._canvas,
      antialias: true,
      powerPreference: 'high-performance',
    });
    this._renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this._renderer.setSize(window.innerWidth, window.innerHeight);
    this._renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this._renderer.toneMappingExposure = this.settings.exposure;
    this._renderer.shadowMap.enabled = true;
    this._renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // Scene
    this._scene = new THREE.Scene();
    this._scene.background = new THREE.Color(C.bgDeep);
    this._scene.fog = new THREE.FogExp2(C.bgDeep, 0.005);

    // Camera
    this._camera = new THREE.PerspectiveCamera(
      this.settings.fov, window.innerWidth / window.innerHeight, 0.1, 300
    );
    this._camera.position.set(6, 5, 8);
    this._camera.lookAt(0, 1.2, 0);

    // Controls
    this._controls = new OrbitControls(this._camera, this._canvas);
    this._controls.enableDamping = true;
    this._controls.dampingFactor = 0.08;
    this._controls.minDistance = 2;
    this._controls.maxDistance = 25;
    this._controls.maxPolarAngle = Math.PI * 0.88;
    this._controls.target.set(0, 1.2, 0);
    this._controls.update();

    this._clock = new THREE.Clock();

    // Data
    this._demoData = new DemoDataGenerator();
    this._demoData.setCycleDuration(this.settings.cycle || 30);
    if (this.settings.scenario && this.settings.scenario !== 'auto') {
      this._demoData.setScenario(this.settings.scenario);
    }
    this._currentData = null;
    this._currentScenario = null;

    // Build scene
    this._setupLighting();
    this._nebula = new NebulaBackground(this._scene);
    this._buildRoom();
    this._buildRouter();
    this._poseSystem = new PoseSystem();
    this._figurePool = new FigurePool(this._scene, this.settings, this._poseSystem);
    this._scenarioProps = new ScenarioProps(this._scene);
    this._buildDotMatrixMist();
    this._buildParticleTrail();
    this._buildWifiWaves();
    this._buildSignalField();
    this._buildCSIHeatmapPanel();
    this._buildPhasePlotPanel();
    this._buildDopplerSpectrumPanel();
    this._buildSignalFieldFloor();
    this._buildVitalsOracle();
    this._buildPhaseConstellation();
    this._enhanceSignalFieldFloorZones();

    // Post-processing
    this._postProcessing = new PostProcessing(this._renderer, this._scene, this._camera);
    this._applyPostSettings();

    // HUD controller (settings dialog, sparkline, vital displays)
    this._hud = new HudController(this);

    // State
    this._autopilot = false;
    this._autoAngle = 0;
    this._fpsFrames = 0;
    this._fpsTime = 0;
    this._fpsValue = 60;
    this._showFps = false;
    this._qualityLevel = 2;

    // WebSocket for live data — always try auto-detect on startup
    this._ws = null;
    this._liveData = null;
    this._liveState = this._createLiveState();
    this._autoDetecting = true;
    this._autoDetectLive();

    // Input
    this._initKeyboard();
    this._hud.initSettings();
    this._hud.initQuickSelect();
    this._hud.initHUDOverlay();
    window.addEventListener('resize', () => this._onResize());

    // Start
    this._animate();
  }

  // ---- Lighting ----

  _setupLighting() {
    this._ambient = new THREE.AmbientLight(0xccccdd, this.settings.ambient * 5.0);
    this._scene.add(this._ambient);

    const hemi = new THREE.HemisphereLight(0x6688bb, 0x203040, 1.2);
    this._scene.add(hemi);

    const key = new THREE.DirectionalLight(0xffeedd, 1.2);
    key.position.set(4, 8, 3);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.near = 0.5;
    key.shadow.camera.far = 20;
    key.shadow.camera.left = -8;
    key.shadow.camera.right = 8;
    key.shadow.camera.top = 8;
    key.shadow.camera.bottom = -8;
    this._scene.add(key);

    // Fill light from opposite side
    const fill = new THREE.DirectionalLight(0x8899bb, 0.7);
    fill.position.set(-4, 5, -2);
    this._scene.add(fill);

    // Rim light from above/behind for edge definition
    const rim = new THREE.DirectionalLight(0x6699cc, 0.5);
    rim.position.set(0, 6, -5);
    this._scene.add(rim);

    // Overhead room light — general illumination
    const overhead = new THREE.PointLight(0x8899aa, 1.0, 20, 1.0);
    overhead.position.set(0, 3.8, 0);
    this._scene.add(overhead);
  }

  // ---- Room ----

  _buildRoom() {
    this._grid = new THREE.GridHelper(12, 24, 0x1a4830, 0x0c2818);
    this._grid.material.opacity = 0.5;
    this._grid.material.transparent = true;
    this._scene.add(this._grid);

    const boxGeo = new THREE.BoxGeometry(12, 4, 10);
    const edges = new THREE.EdgesGeometry(boxGeo);
    this._roomWire = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({
      color: C.greenDim, opacity: 0.3, transparent: true,
    }));
    this._roomWire.position.y = 2;
    this._scene.add(this._roomWire);

    // Reflective floor
    const floorGeo = new THREE.PlaneGeometry(12, 10);
    this._floorMat = new THREE.MeshStandardMaterial({
      color: 0x101810,
      roughness: 1.0 - this.settings.reflect * 0.7,
      metalness: this.settings.reflect * 0.5,
      emissive: 0x020404,
      emissiveIntensity: 0.08,
    });
    const floor = new THREE.Mesh(floorGeo, this._floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    this._scene.add(floor);

    // Table under router
    const tableGeo = new THREE.BoxGeometry(0.8, 0.6, 0.5);
    const tableMat = new THREE.MeshStandardMaterial({ color: 0x6b5840, roughness: 0.55, emissive: 0x1a1408, emissiveIntensity: 0.25 });
    const table = new THREE.Mesh(tableGeo, tableMat);
    table.position.set(-4, 0.3, -3);
    table.castShadow = true;
    this._scene.add(table);
  }

  // ---- Router ----

  _buildRouter() {
    this._routerGroup = new THREE.Group();
    this._routerGroup.position.set(-4, 0.92, -3);

    const bodyGeo = new THREE.BoxGeometry(0.6, 0.12, 0.35);
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x505060, roughness: 0.2, metalness: 0.7, emissive: 0x101018, emissiveIntensity: 0.2 });
    this._routerGroup.add(new THREE.Mesh(bodyGeo, bodyMat));

    for (let i = -1; i <= 1; i++) {
      const antGeo = new THREE.CylinderGeometry(0.015, 0.015, 0.35);
      const antMat = new THREE.MeshStandardMaterial({ color: 0x606068, roughness: 0.3, metalness: 0.6, emissive: 0x101018, emissiveIntensity: 0.15 });
      const ant = new THREE.Mesh(antGeo, antMat);
      ant.position.set(i * 0.2, 0.24, 0);
      ant.rotation.z = i * 0.15;
      this._routerGroup.add(ant);
    }

    const ledGeo = new THREE.SphereGeometry(0.025);
    this._routerLed = new THREE.Mesh(ledGeo, new THREE.MeshBasicMaterial({ color: C.greenGlow }));
    this._routerLed.position.set(0.22, 0.07, 0.18);
    this._routerGroup.add(this._routerLed);

    this._routerLight = new THREE.PointLight(C.blueSignal, 1.2, 8);
    this._routerLight.position.set(0, 0.3, 0);
    this._routerGroup.add(this._routerLight);

    this._scene.add(this._routerGroup);
  }

  // ---- WiFi Waves ----

  _buildWifiWaves() {
    this._wifiWaves = [];
    for (let i = 0; i < 5; i++) {
      const radius = 0.8 + i * 1.0;
      const geo = new THREE.SphereGeometry(radius, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.6);
      const mat = new THREE.MeshBasicMaterial({
        color: C.blueSignal,
        transparent: true, opacity: 0,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false, wireframe: true,
      });
      const shell = new THREE.Mesh(geo, mat);
      shell.position.copy(this._routerGroup.position);
      shell.position.y += 0.5;
      this._scene.add(shell);
      this._wifiWaves.push({ mesh: shell, mat, phase: i * 0.7 });
    }
  }

  // ========================================
  // DOT MATRIX MIST
  // ========================================

  _buildDotMatrixMist() {
    const COUNT = 800;
    const positions = new Float32Array(COUNT * 3);
    const alphas = new Float32Array(COUNT);
    for (let i = 0; i < COUNT; i++) {
      const angle = Math.random() * Math.PI * 2;
      const r = Math.random() * 0.5;
      positions[i * 3] = Math.cos(angle) * r;
      positions[i * 3 + 1] = Math.random() * 1.8;
      positions[i * 3 + 2] = Math.sin(angle) * r;
      alphas[i] = 0;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('alpha', new THREE.BufferAttribute(alphas, 1));
    const mat = new THREE.ShaderMaterial({
      vertexShader: `
        attribute float alpha;
        varying float vAlpha;
        void main() {
          vAlpha = alpha;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = 3.0 * (200.0 / -mv.z);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        varying float vAlpha;
        void main() {
          float d = length(gl_PointCoord - 0.5);
          if (d > 0.5) discard;
          float edge = smoothstep(0.5, 0.2, d);
          gl_FragColor = vec4(uColor, edge * vAlpha);
        }
      `,
      uniforms: { uColor: { value: new THREE.Color(this.settings.wireColor) } },
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    this._mistPoints = new THREE.Points(geo, mat);
    this._scene.add(this._mistPoints);
    this._mistCount = COUNT;
  }

  // ---- Particle Trail ----

  _buildParticleTrail() {
    const COUNT = 200;
    const positions = new Float32Array(COUNT * 3);
    const ages = new Float32Array(COUNT);
    for (let i = 0; i < COUNT; i++) ages[i] = 1;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('age', new THREE.BufferAttribute(ages, 1));
    const mat = new THREE.ShaderMaterial({
      vertexShader: `
        attribute float age;
        varying float vAge;
        void main() {
          vAge = age;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = max(1.0, (1.0 - age) * 5.0 * (150.0 / -mv.z));
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        varying float vAge;
        void main() {
          float d = length(gl_PointCoord - 0.5);
          if (d > 0.5) discard;
          float alpha = (1.0 - vAge) * 0.6 * smoothstep(0.5, 0.1, d);
          gl_FragColor = vec4(uColor, alpha);
        }
      `,
      uniforms: { uColor: { value: new THREE.Color(C.greenGlow) } },
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    this._trail = new THREE.Points(geo, mat);
    this._scene.add(this._trail);
    this._trailHead = 0;
    this._trailCount = COUNT;
    this._trailTimer = 0;
  }

  // ---- Signal Field ----

  _buildSignalField() {
    const gridSize = 20;
    const count = gridSize * gridSize;
    const positions = new Float32Array(count * 3);
    this._fieldColors = new Float32Array(count * 3);
    this._fieldSizes = new Float32Array(count);
    for (let iz = 0; iz < gridSize; iz++) {
      for (let ix = 0; ix < gridSize; ix++) {
        const idx = iz * gridSize + ix;
        positions[idx * 3] = (ix - gridSize / 2) * 0.6;
        positions[idx * 3 + 1] = 0.02;
        positions[idx * 3 + 2] = (iz - gridSize / 2) * 0.5;
        this._fieldSizes[idx] = 8;
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(this._fieldColors, 3));
    geo.setAttribute('size', new THREE.BufferAttribute(this._fieldSizes, 1));
    this._fieldMat = new THREE.PointsMaterial({
      size: 0.35, vertexColors: true, transparent: true,
      opacity: this.settings.field, blending: THREE.AdditiveBlending,
      depthWrite: false, sizeAttenuation: true,
    });
    this._fieldPoints = new THREE.Points(geo, this._fieldMat);
    this._scene.add(this._fieldPoints);
  }

  // ---- Keyboard ----

  _initKeyboard() {
    window.addEventListener('keydown', (e) => {
      if (this._hud.settingsOpen) return;
      switch (e.key.toLowerCase()) {
        case 'a':
          this._autopilot = !this._autopilot;
          this._controls.enabled = !this._autopilot;
          break;
        case 'd': this._demoData.cycleScenario(); break;
        case 'f':
          this._showFps = !this._showFps;
          document.getElementById('fps-counter').style.display = this._showFps ? 'block' : 'none';
          break;
        case 's': this._hud.toggleSettings(); break;
        case ' ':
          e.preventDefault();
          this._demoData.paused = !this._demoData.paused;
          break;
      }
    });
  }

  // ---- Settings / HUD methods delegated to HudController ----

  _applyPostSettings() {
    const pp = this._postProcessing;
    pp._bloomPass.strength = this.settings.bloom;
    pp._bloomPass.radius = this.settings.bloomRadius;
    pp._bloomPass.threshold = this.settings.bloomThresh;
    pp._vignettePass.uniforms.uVignetteStrength.value = this.settings.vignette;
    pp._vignettePass.uniforms.uGrainStrength.value = this.settings.grain;
    pp._vignettePass.uniforms.uChromaticStrength.value = this.settings.chromatic;
  }

  _applyColors() {
    const wc = new THREE.Color(this.settings.wireColor);
    const jc = new THREE.Color(this.settings.jointColor);
    this._figurePool.applyColors(wc, jc);
    this._mistPoints.material.uniforms.uColor.value.copy(wc);
  }

  // ---- WebSocket live data ----

  _createLiveState() {
    return {
      devices: new Map(),
      zones: [],
      lastSignal: null,
      lastVitals: null,
      lastVitalsAt: 0,
      lastEvent: null,
      lastUpdateAt: 0,
    };
  }

  _resetLiveState() {
    this._liveState = this._createLiveState();
    this._liveData = null;
  }

  _snapshotDevices() {
    return Array.from(this._liveState.devices.values());
  }

  _applyLiveMessage(message) {
    if (!message || typeof message !== 'object') return;

    const { type, payload = {} } = message;
    if (type === 'init') {
      this._liveState.devices = new Map((payload.devices || []).map((device) => [device.id, device]));
      this._liveState.zones = payload.zones || [];
    } else if (type === 'device_update') {
      this._liveState.devices = new Map((payload.devices || []).map((device) => [device.id, device]));
    } else if (type === 'zone_update') {
      this._liveState.zones = payload.zones || [];
    } else if (type === 'signal') {
      this._liveState.lastSignal = payload;
    } else if (type === 'vitals') {
      this._liveState.lastVitals = payload;
      this._liveState.lastVitalsAt = Date.now();
    } else if (type === 'event') {
      this._liveState.lastEvent = payload;
    } else {
      return;
    }

    this._liveState.lastUpdateAt = Date.now();
    this._liveData = this._buildLiveFrame();
  }

  _deviceToPerson(device, index, latestDeviceId) {
    const xSlots = [-2.8, 2.8, -1.4, 1.4, 0, 0];
    const zSlots = [-1.8, -1.8, 1.8, 1.8, -3.2, 3.2];
    const x = xSlots[index % xSlots.length];
    const z = zSlots[index % zSlots.length];
    const signalStrength = device.signalStrength ?? -60;
    const motionScore = latestDeviceId === device.id ? 85 : 18;
    const pose = motionScore > 50 ? 'walking' : (motionScore > 30 ? 'standing' : 'sitting');
    return {
      id: device.id,
      position: [x, 0, z],
      motion_score: motionScore,
      pose,
      facing: index % 2 === 0 ? Math.PI * 0.15 : Math.PI * 0.85,
      signal_strength: signalStrength,
    };
  }

  _generateExtraPersons(count, startIndex) {
    // Generate additional persons beyond detected devices based on presenceCount
    const xSlots = [-2.0, 2.0, -0.7, 0.7, -2.4, 2.4, -1.5, 1.5, 0, -3.0];
    const zSlots = [0, 0, -1.0, 1.0, -2.5, 2.5, 2.0, -2.0, -3.0, 1.5];
    const persons = [];
    for (let i = 0; i < count; i++) {
      const idx = startIndex + i;
      persons.push({
        id: `p${idx}`,
        position: [xSlots[idx % xSlots.length], 0, zSlots[idx % zSlots.length]],
        motion_score: 10 + Math.round(Math.random() * 15),
        pose: 'sitting',
        facing: (idx * 0.7) % (Math.PI * 2),
      });
    }
    return persons;
  }

  _buildSignalFieldData(personCount) {
    const values = [];
    for (let iz = 0; iz < 20; iz++) {
      for (let ix = 0; ix < 20; ix++) {
        const nx = (ix - 10) / 10;
        const nz = (iz - 10) / 10;
        const radius = Math.sqrt(nx * nx + nz * nz);
        const intensity = Math.max(0.04, personCount * 0.08 - radius * 0.03);
        values.push(intensity);
      }
    }
    return { grid_size: [20, 1, 20], values };
  }

  _buildLiveFrame() {
    const devices = this._snapshotDevices();
    const onlineDevices = devices.filter((device) => device.status !== 'offline');
    const lastSignal = this._liveState.lastSignal;
    const vitalsTtlMs = 15000;
    const lastVitals = Date.now() - (this._liveState.lastVitalsAt || 0) <= vitalsTtlMs
      ? this._liveState.lastVitals
      : null;
    const lastEvent = this._liveState.lastEvent;
    const latestDeviceId = lastSignal?.device_id || lastEvent?.deviceId || onlineDevices[0]?.id || null;
    const meanRssi = devices.length > 0
      ? devices.reduce((sum, device) => sum + (device.signalStrength ?? -65), 0) / devices.length
      : -65;
    const motionIndex = lastSignal?.motion_index ?? (onlineDevices.length > 0 ? 0.12 : 0);
    const personCount = this._liveState.zones[0]?.presenceCount || 0;
    // Generate persons based on presenceCount (CSI-detected people), not device count
    const persons = this._generateExtraPersons(personCount, 0);
    const hasFall = lastEvent?.type === 'fall_suspected';
    const scenario = hasFall
      ? 'fall_event'
      : personCount >= 2
        ? 'two_walking'
        : personCount === 1
          ? 'single_breathing'
          : 'empty_room';

    return {
      type: 'sensing_update',
      timestamp: Date.now() / 1000,
      source: 'hardware',
      scenario,
      nodes: devices.map((device, index) => ({
        node_id: Number.parseInt(String(device.id).replace(/^node-/, ''), 10) || index + 1,
        rssi_dbm: device.signalStrength ?? -65,
        position: [device.x || 0, 0, device.y || 0],
        amplitude: new Float32Array(64),
        subcarrier_count: 64,
      })),
      features: {
        mean_rssi: meanRssi,
        variance: Math.max(0.05, Math.abs(motionIndex) * 0.8),
        std: Math.max(0.1, Math.abs(motionIndex) * 0.5),
        motion_band_power: Math.max(0, motionIndex),
        breathing_band_power: personCount > 0 ? 0.08 : 0,
        dominant_freq_hz: personCount > 0 ? 0.23 : 0.02,
        spectral_power: Math.max(0.02, Math.abs(motionIndex) * 0.9),
      },
      classification: {
        motion_level: motionIndex > 0.15 ? 'active' : (personCount > 0 ? 'present_still' : 'absent'),
        presence: personCount > 0,
        confidence: personCount > 0 ? 0.92 : 0.75,
        fall_detected: hasFall,
      },
      signal_field: this._buildSignalFieldData(personCount),
      vital_signs: (() => {
        // P2-9: When no dedicated vitals message, aggregate from device-level data
        if (lastVitals) {
          return {
            breathing_rate_bpm: lastVitals.breathing_rate_bpm || (personCount > 0 ? 15 : 0),
            heart_rate_bpm: lastVitals.heart_rate_bpm || (personCount > 0 ? 76 : 0),
            breathing_confidence: 0.7,
            heart_rate_confidence: 0.5,
          };
        }
        // Aggregate breathing_bpm and heart_rate from online devices
        let breathSum = 0, breathCount = 0, hrSum = 0, hrCount = 0;
        for (const dev of onlineDevices) {
          if (dev.breathing_bpm > 0) { breathSum += dev.breathing_bpm; breathCount++; }
          if (dev.heart_rate > 0 || dev.csi_heart_rate > 0) {
            hrSum += (dev.heart_rate || dev.csi_heart_rate || 0);
            hrCount++;
          }
        }
        const aggBreathing = breathCount > 0 ? breathSum / breathCount : (personCount > 0 ? 15 : 0);
        const aggHr = hrCount > 0 ? hrSum / hrCount : (personCount > 0 ? 76 : 0);
        return {
          breathing_rate_bpm: aggBreathing,
          heart_rate_bpm: aggHr,
          breathing_confidence: breathCount > 0 ? 0.65 : (personCount > 0 ? 0.55 : 0),
          heart_rate_confidence: hrCount > 0 ? 0.45 : (personCount > 0 ? 0.35 : 0),
        };
      })(),
      persons,
      estimated_persons: personCount,
      edge_modules: {},
      _observatory: { subcarrier_iq: [], per_subcarrier_variance: new Float32Array(64).fill(0.02) },
    };
  }

  _autoDetectLive() {
    // Probe sensing server health — prioritize signal-adapter port
    const host = window.location.hostname || 'localhost';
    const candidates = [
      `http://${host}:8001`,                     // RuView signal adapter (priority)
      window.location.origin,                   // same origin (vite proxy)
      `http://${host}:8765`,                     // default WS port
      `http://${host}:3000`,                     // default HTTP port
    ];
    // Deduplicate
    const unique = [...new Set(candidates)];

    console.log('[Observatory] Auto-detect candidates:', unique);
    const tryNext = async (i) => {
      if (i >= unique.length) {
        console.log('[Observatory] No sensing server detected, using demo mode');
        this._autoDetecting = false;
        return;
      }
      const base = unique[i];
      console.log(`[Observatory] Trying ${base}/health ...`);
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 10000);
        const r = await fetch(`${base}/health`, { signal: controller.signal });
        clearTimeout(timer);
        if (!r.ok) { tryNext(i + 1); return; }
        const text = await r.text();
        const data = JSON.parse(text);
        if (data && data.status === 'ok') {
          const wsProto = base.startsWith('https') ? 'wss:' : 'ws:';
          const urlObj = new URL(base);
          const wsUrl = `${wsProto}//${urlObj.host}/ws/events`;
          console.log('[Observatory] Live server found:', base, '->', wsUrl);
          this.settings.dataSource = 'ws';
          this.settings.wsUrl = wsUrl;
          this._autoDetecting = false;
          this._connectWS(wsUrl);
        } else {
          tryNext(i + 1);
        }
      } catch (err) {
        console.log(`[Observatory] ${base} failed:`, err.message || err);
        tryNext(i + 1);
      }
    };
    tryNext(0);
  }

  _connectWS(url) {
    this._disconnectWS();
    try {
      this._ws = new WebSocket(url);
      this._ws.onopen = () => {
        console.log('[Observatory] WebSocket connected');
        this._hud.updateSourceBadge('ws', this._ws);
      };
      this._ws.onmessage = (evt) => {
        try {
          this._applyLiveMessage(JSON.parse(evt.data));
        } catch {}
      };
      this._ws.onclose = () => {
        this._ws = null;
        // Don't fall back to demo if auto-detect is still running
        if (!this._autoDetecting) {
          console.log('[Observatory] WebSocket closed, falling back to demo');
          this.settings.dataSource = 'demo';
          this._resetLiveState();
          this._hud.updateSourceBadge('demo', null);
        }
      };
      this._ws.onerror = () => {};
    } catch {}
  }

  _disconnectWS() {
    if (this._ws) { this._ws.close(); this._ws = null; }
    this._resetLiveState();
  }

  // ========================================
  // ANIMATION LOOP
  // ========================================

  _animate() {
    requestAnimationFrame(() => this._animate());
    const dt = Math.min(this._clock.getDelta(), 0.1);
    const elapsed = this._clock.getElapsedTime();

    // Data source
    if (this.settings.dataSource === 'ws' && this._liveData) {
      this._currentData = this._liveData;
    } else {
      this._currentData = this._demoData.update(dt);
    }
    const data = this._currentData;

    // Updates
    this._nebula.update(dt, elapsed);
    this._figurePool.update(data, elapsed);
    this._scenarioProps.update(data, data?.scenario || this._demoData.currentScenario);
    this._updateDotMatrixMist(data, elapsed);
    this._updateParticleTrail(data, dt, elapsed);
    this._updateWifiWaves(elapsed);
    this._updateSignalField(data);
    this._updateCSIHeatmapPanel(data, elapsed);
    this._updatePhasePlotPanel(data, elapsed);
    this._updateDopplerSpectrumPanel(data, elapsed);
    this._updateSignalFieldFloor(data, elapsed);
    this._updateVitalsOracle(data, elapsed);
    this._updatePhaseConstellation(data, elapsed);
    this._hud.tickFPS();
    this._hud.updateHUD(data, this._demoData);
    this._hud.updateSparkline(data);

    // Router LED
    this._routerLed.material.opacity = 0.5 + 0.5 * Math.sin(elapsed * 8);
    this._routerLight.intensity = 0.3 + 0.2 * Math.sin(elapsed * 3);

    // Autopilot orbit
    if (this._autopilot) {
      this._autoAngle += dt * this.settings.orbitSpeed;
      const r = 10;
      this._camera.position.set(
        Math.sin(this._autoAngle) * r,
        4.5 + Math.sin(this._autoAngle * 0.5),
        Math.cos(this._autoAngle) * r
      );
      this._controls.target.set(0, 1.2, 0);
      this._controls.update();
    }
    this._controls.update();
    this._postProcessing.update(elapsed);
    this._postProcessing.render();
    this._updateFPS(dt);
  }


  // ========================================
  // MIST & TRAIL
  // ========================================

  _updateDotMatrixMist(data, elapsed) {
    const persons = data?.persons || [];
    const isPresent = data?.classification?.presence || false;
    const pos = this._mistPoints.geometry.attributes.position;
    const alpha = this._mistPoints.geometry.attributes.alpha;

    if (!isPresent || persons.length === 0) {
      for (let i = 0; i < this._mistCount; i++) {
        alpha.array[i] = Math.max(0, alpha.array[i] - 0.02);
      }
      alpha.needsUpdate = true;
      return;
    }

    // Follow primary person
    const pp = persons[0].position || [0, 0, 0];
    const px = pp[0] || 0, pz = pp[2] || 0;
    const ms = persons[0].motion_score || 0;
    const pose = persons[0].pose || 'standing';
    const isLying = pose === 'lying' || pose === 'fallen';
    const bodyH = isLying ? 0.4 : 1.7;
    const bodyBaseY = isLying ? (pp[1] || 0) + 0.05 : 0.05;
    const spread = ms > 50 ? 0.6 : 0.4;

    for (let i = 0; i < this._mistCount; i++) {
      const drift = Math.sin(elapsed * 0.5 + i * 0.1) * 0.003;
      const angle = (i / this._mistCount) * Math.PI * 2 + elapsed * 0.1;
      const layerT = (i % 20) / 20;
      const layerY = bodyBaseY + layerT * bodyH;

      let bodyWidth;
      if (isLying) {
        bodyWidth = 0.25;
      } else {
        bodyWidth = layerT > 0.75 ? 0.15 : (layerT > 0.45 ? 0.25 : 0.18);
      }
      const r = bodyWidth * (0.5 + 0.5 * Math.sin(i * 1.7 + elapsed * 0.3)) * spread;

      const tx = px + Math.cos(angle + i * 0.3) * r + drift;
      const tz = pz + Math.sin(angle + i * 0.5) * r * 0.6;

      pos.array[i * 3] += (tx - pos.array[i * 3]) * 0.05;
      pos.array[i * 3 + 1] += (layerY - pos.array[i * 3 + 1]) * 0.05;
      pos.array[i * 3 + 2] += (tz - pos.array[i * 3 + 2]) * 0.05;

      const targetAlpha = 0.15 + Math.sin(elapsed * 2 + i * 0.5) * 0.08;
      alpha.array[i] += (targetAlpha - alpha.array[i]) * 0.08;
    }
    pos.needsUpdate = true;
    alpha.needsUpdate = true;
  }

  _updateParticleTrail(data, dt, elapsed) {
    if (this.settings.trail <= 0) return;
    const persons = data?.persons || [];
    const isPresent = data?.classification?.presence || false;
    const pos = this._trail.geometry.attributes.position;
    const ages = this._trail.geometry.attributes.age;

    for (let i = 0; i < this._trailCount; i++) {
      ages.array[i] = Math.min(1, ages.array[i] + dt * 0.8);
    }

    // Emit from all active persons
    if (isPresent && persons.length > 0) {
      this._trailTimer += dt;
      const ms = persons[0].motion_score || 0;
      const emitRate = ms > 50 ? 0.02 : 0.08;

      if (this._trailTimer >= emitRate) {
        this._trailTimer = 0;
        for (const p of persons) {
          const pp = p.position || [0, 0, 0];
          const idx = this._trailHead;
          pos.array[idx * 3] = (pp[0] || 0) + (Math.random() - 0.5) * 0.15;
          pos.array[idx * 3 + 1] = Math.random() * 1.5 + 0.1;
          pos.array[idx * 3 + 2] = (pp[2] || 0) + (Math.random() - 0.5) * 0.15;
          ages.array[idx] = 0;
          this._trailHead = (this._trailHead + 1) % this._trailCount;
        }
      }
    }
    pos.needsUpdate = true;
    ages.needsUpdate = true;
  }

  // ---- WiFi Waves ----

  _updateWifiWaves(elapsed) {
    for (const w of this._wifiWaves) {
      const t = (elapsed * 0.8 + w.phase) % 4.5;
      const life = t / 4.5;
      w.mat.opacity = Math.max(0, this.settings.waves * 0.25 * (1 - life));
      const scale = 1 + life * 0.6;
      w.mesh.scale.set(scale, scale, scale);
      w.mesh.rotation.y = elapsed * 0.05;
    }
  }

  // ---- Signal Field ----

  _updateSignalField(data) {
    const field = data?.signal_field?.values;
    if (!field) return;
    const count = Math.min(field.length, 400);
    for (let i = 0; i < count; i++) {
      const v = field[i] || 0;
      let r, g, b;
      if (v < 0.3) { r = 0; g = v * 1.5; b = v * 0.3; }
      else if (v < 0.6) {
        const t = (v - 0.3) / 0.3;
        r = t * 0.3; g = 0.45 + t * 0.4; b = 0.09 - t * 0.05;
      } else {
        const t = (v - 0.6) / 0.4;
        r = 0.3 + t * 0.7; g = 0.85 - t * 0.2; b = 0.04;
      }
      this._fieldColors[i * 3] = r;
      this._fieldColors[i * 3 + 1] = g;
      this._fieldColors[i * 3 + 2] = b;
      this._fieldSizes[i] = 5 + v * 15;
    }
    this._fieldPoints.geometry.attributes.color.needsUpdate = true;
    this._fieldPoints.geometry.attributes.size.needsUpdate = true;
  }

  // ========================================
  // CSI AMPLITUDE HEATMAP PANEL
  // ========================================

  _buildCSIHeatmapPanel() {
    // Floating holographic panel showing CSI amplitude heatmap
    // 30 subcarriers x 40 time slots, rendered via canvas texture
    this._csiGroup = new THREE.Group();
    this._csiGroup.name = 'csi-heatmap-panel';
    this._csiGroup.position.set(-5.2, 3.2, -3.5);
    // Slight tilt for holographic look
    this._csiGroup.rotation.y = 0.3;
    this._csiGroup.rotation.x = -0.05;

    const panelW = 2.4;
    const panelH = 1.6;

    // Canvas for heatmap texture
    this._csiCanvas = document.createElement('canvas');
    this._csiCanvas.width = 300;  // 30 subcarriers * 10px
    this._csiCanvas.height = 400; // 40 time slots * 10px
    this._csiCtx = this._csiCanvas.getContext('2d');
    this._csiCtx.fillStyle = '#000011';
    this._csiCtx.fillRect(0, 0, 300, 400);

    this._csiTexture = new THREE.CanvasTexture(this._csiCanvas);
    this._csiTexture.minFilter = THREE.LinearFilter;
    this._csiTexture.magFilter = THREE.LinearFilter;

    // Main heatmap plane
    const planeGeo = new THREE.PlaneGeometry(panelW, panelH);
    const planeMat = new THREE.MeshBasicMaterial({
      map: this._csiTexture,
      transparent: true,
      opacity: 0.88,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const heatmapPlane = new THREE.Mesh(planeGeo, planeMat);
    this._csiGroup.add(heatmapPlane);

    // Border frame for holographic feel
    const frameGeo = new THREE.EdgesGeometry(new THREE.PlaneGeometry(panelW + 0.08, panelH + 0.08));
    const frameMat = new THREE.LineBasicMaterial({ color: 0x2090ff, opacity: 0.5, transparent: true });
    const frame = new THREE.LineSegments(frameGeo, frameMat);
    frame.position.z = 0.001;
    this._csiGroup.add(frame);

    // Title label
    const titleSprite = this._createHoloLabel('CSI AMPLITUDE', 0x5588cc);
    titleSprite.position.set(0, panelH / 2 + 0.15, 0);
    titleSprite.scale.set(1.2, 0.2, 1);
    this._csiGroup.add(titleSprite);

    // Axis labels
    const subLabel = this._createHoloLabel('SUBCARRIER', 0x446688);
    subLabel.position.set(0, -panelH / 2 - 0.12, 0);
    subLabel.scale.set(0.9, 0.15, 1);
    this._csiGroup.add(subLabel);

    const timeLabel = this._createHoloLabel('TIME', 0x446688);
    timeLabel.position.set(-panelW / 2 - 0.2, 0, 0);
    timeLabel.scale.set(0.5, 0.15, 1);
    this._csiGroup.add(timeLabel);

    this._scene.add(this._csiGroup);

    // Amplitude history ring buffer
    this._csiAmplitudeHistory = [];
    for (let i = 0; i < 40; i++) {
      this._csiAmplitudeHistory.push(new Float32Array(30));
    }
    this._csiTimeIndex = 0;
  }

  _createHoloLabel(text, color) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 256;
    canvas.height = 48;
    ctx.font = '13px monospace';
    ctx.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, 128, 24);
    const tex = new THREE.CanvasTexture(canvas);
    tex.needsUpdate = true;
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
    return new THREE.Sprite(mat);
  }

  _updateCSIHeatmapPanel(data, elapsed) {
    if (!this._csiGroup) return;

    // Generate CSI amplitude from signal data or synthesize from features
    const amplitude = new Float32Array(30);
    const feat = data?.features || {};
    const motionPower = feat.motion_band_power || 0;
    const variance = feat.variance || 0;

    for (let s = 0; s < 30; s++) {
      // Synthesize amplitude from scene data, mimicking real CSI patterns
      const baseFreq = Math.sin(elapsed * 2.0 + s * 0.3) * 0.25;
      const bodyEffect = Math.sin(elapsed * 0.8 + s * 0.15) * variance * 0.5;
      const noise = (Math.random() - 0.5) * 0.06;
      amplitude[s] = Math.max(0, Math.min(1, 0.3 + motionPower * 0.4 + baseFreq + bodyEffect + noise));
    }

    // P2-10: Ring buffer — overwrite at _csiTimeIndex instead of shift()
    this._csiAmplitudeHistory[this._csiTimeIndex].set(amplitude);
    this._csiTimeIndex = (this._csiTimeIndex + 1) % 40;

    // Render heatmap to canvas
    const ctx = this._csiCtx;
    const cellW = 10; // 300 / 30
    const cellH = 10; // 400 / 40

    for (let t = 0; t < 40; t++) {
      // Read from ring buffer: oldest entry is at _csiTimeIndex, newest at _csiTimeIndex-1
      const row = this._csiAmplitudeHistory[(this._csiTimeIndex + t) % 40];
      for (let s = 0; s < 30; s++) {
        const val = row[s] || 0;
        // Color: blue(quiet) -> cyan -> green -> yellow -> red(active)
        // HSL hue: 0.6 (blue) -> 0 (red)
        const hue = 0.6 - val * 0.6;
        const sat = 0.9;
        const light = 0.08 + val * 0.52;
        ctx.fillStyle = `hsl(${Math.round(hue * 360)}, ${Math.round(sat * 100)}%, ${Math.round(light * 100)}%)`;
        ctx.fillRect(s * cellW, (39 - t) * cellH, cellW, cellH);
      }
    }

    this._csiTexture.needsUpdate = true;

    // Subtle panel float animation
    this._csiGroup.position.y = 3.2 + Math.sin(elapsed * 0.7) * 0.05;
  }

  // ========================================
  // PHASE PLOT PANEL
  // ========================================

  _buildPhasePlotPanel() {
    // Floating panel showing phase across subcarriers as a line graph
    // Positioned next to the CSI heatmap, slightly lower
    this._phaseGroup = new THREE.Group();
    this._phaseGroup.name = 'phase-plot-panel';
    this._phaseGroup.position.set(-5.2 + 2.7, 3.0, -3.5);
    this._phaseGroup.rotation.y = 0.3;
    this._phaseGroup.rotation.x = -0.05;

    const panelW = 2.0;
    const panelH = 1.0;

    // Canvas for phase plot texture (256x128)
    this._phaseCanvas = document.createElement('canvas');
    this._phaseCanvas.width = 256;
    this._phaseCanvas.height = 128;
    this._phaseCtx = this._phaseCanvas.getContext('2d');
    this._phaseCtx.fillStyle = '#000011';
    this._phaseCtx.fillRect(0, 0, 256, 128);

    this._phaseTexture = new THREE.CanvasTexture(this._phaseCanvas);
    this._phaseTexture.minFilter = THREE.LinearFilter;
    this._phaseTexture.magFilter = THREE.LinearFilter;

    // Phase plot plane
    const planeGeo = new THREE.PlaneGeometry(panelW, panelH);
    const planeMat = new THREE.MeshBasicMaterial({
      map: this._phaseTexture,
      transparent: true,
      opacity: 0.88,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this._phaseGroup.add(new THREE.Mesh(planeGeo, planeMat));

    // Border frame
    const frameGeo = new THREE.EdgesGeometry(new THREE.PlaneGeometry(panelW + 0.06, panelH + 0.06));
    const frameMat = new THREE.LineBasicMaterial({ color: 0x2090ff, opacity: 0.5, transparent: true });
    const frame = new THREE.LineSegments(frameGeo, frameMat);
    frame.position.z = 0.001;
    this._phaseGroup.add(frame);

    // Title label
    const titleSprite = this._createHoloLabel('PHASE PLOT', 0x5588cc);
    titleSprite.position.set(0, panelH / 2 + 0.12, 0);
    titleSprite.scale.set(1.0, 0.18, 1);
    this._phaseGroup.add(titleSprite);

    // Axis labels
    const xLabel = this._createHoloLabel('SUBCARRIER (0-30)', 0x446688);
    xLabel.position.set(0, -panelH / 2 - 0.1, 0);
    xLabel.scale.set(0.9, 0.13, 1);
    this._phaseGroup.add(xLabel);

    const yLabel = this._createHoloLabel('PHASE', 0x446688);
    yLabel.position.set(-panelW / 2 - 0.18, 0, 0);
    yLabel.scale.set(0.4, 0.13, 1);
    this._phaseGroup.add(yLabel);

    this._scene.add(this._phaseGroup);
  }

  _updatePhasePlotPanel(data, elapsed) {
    if (!this._phaseGroup) return;

    const ctx = this._phaseCtx;
    const W = 256;
    const H = 128;

    // Clear with dark background
    ctx.fillStyle = 'rgba(0, 0, 17, 1)';
    ctx.fillRect(0, 0, W, H);

    // Draw grid lines (subtle)
    ctx.strokeStyle = 'rgba(32, 64, 96, 0.3)';
    ctx.lineWidth = 0.5;
    // Horizontal: -pi, 0, pi
    for (let i = 0; i <= 4; i++) {
      const y = (i / 4) * H;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }
    // Vertical: every 5 subcarriers
    for (let s = 0; s <= 30; s += 5) {
      const x = (s / 30) * W;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, H);
      ctx.stroke();
    }

    // Generate or extract phase data for 30 subcarriers
    const nSc = 30;
    const phases = new Float32Array(nSc);
    const feat = data?.features || {};
    const variance = feat.variance || 0;

    for (let s = 0; s < nSc; s++) {
      // Synthesize phase pattern: combine slow drift + body-induced modulation
      const basePhase = Math.sin(elapsed * 0.5 + s * 0.2) * 1.5;
      const bodyMod = Math.sin(elapsed * 1.8 + s * 0.35) * variance * 2.0;
      const noise = (Math.random() - 0.5) * 0.15;
      phases[s] = Math.max(-Math.PI, Math.min(Math.PI, basePhase + bodyMod + noise));
    }

    // Draw phase line plot
    // Y-axis: -pi at bottom, +pi at top
    ctx.beginPath();
    ctx.strokeStyle = '#20d0ff';
    ctx.lineWidth = 2;
    ctx.shadowColor = '#20d0ff';
    ctx.shadowBlur = 4;

    for (let s = 0; s < nSc; s++) {
      const x = (s / (nSc - 1)) * (W - 8) + 4;
      // Map phase [-pi, pi] to canvas Y [H-4, 4] (inverted: pi at top)
      const normalizedY = (phases[s] + Math.PI) / (2 * Math.PI);
      const y = H - 4 - normalizedY * (H - 8);

      if (s === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Draw data points
    ctx.fillStyle = '#60e0ff';
    for (let s = 0; s < nSc; s++) {
      const x = (s / (nSc - 1)) * (W - 8) + 4;
      const normalizedY = (phases[s] + Math.PI) / (2 * Math.PI);
      const y = H - 4 - normalizedY * (H - 8);
      ctx.beginPath();
      ctx.arc(x, y, 2, 0, Math.PI * 2);
      ctx.fill();
    }

    this._phaseTexture.needsUpdate = true;

    // Subtle float animation
    this._phaseGroup.position.y = 3.0 + Math.sin(elapsed * 0.7 + 1.0) * 0.04;
  }

  // ========================================
  // DOPPLER SPECTRUM PANEL
  // ========================================

  _buildDopplerSpectrumPanel() {
    // Floating panel showing 16-bar Doppler frequency distribution
    // Positioned below the CSI heatmap
    this._dopplerGroup = new THREE.Group();
    this._dopplerGroup.name = 'doppler-spectrum-panel';
    this._dopplerGroup.position.set(-5.2, 1.4, -3.5);
    this._dopplerGroup.rotation.y = 0.3;
    this._dopplerGroup.rotation.x = -0.05;

    const panelW = 2.0;
    const panelH = 1.0;

    // Canvas for Doppler spectrum texture (256x128)
    this._dopplerCanvas = document.createElement('canvas');
    this._dopplerCanvas.width = 256;
    this._dopplerCanvas.height = 128;
    this._dopplerCtx = this._dopplerCanvas.getContext('2d');
    this._dopplerCtx.fillStyle = '#000011';
    this._dopplerCtx.fillRect(0, 0, 256, 128);

    this._dopplerTexture = new THREE.CanvasTexture(this._dopplerCanvas);
    this._dopplerTexture.minFilter = THREE.LinearFilter;
    this._dopplerTexture.magFilter = THREE.LinearFilter;

    // Doppler spectrum plane
    const planeGeo = new THREE.PlaneGeometry(panelW, panelH);
    const planeMat = new THREE.MeshBasicMaterial({
      map: this._dopplerTexture,
      transparent: true,
      opacity: 0.88,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this._dopplerGroup.add(new THREE.Mesh(planeGeo, planeMat));

    // Border frame
    const frameGeo = new THREE.EdgesGeometry(new THREE.PlaneGeometry(panelW + 0.06, panelH + 0.06));
    const frameMat = new THREE.LineBasicMaterial({ color: 0x2090ff, opacity: 0.5, transparent: true });
    const frame = new THREE.LineSegments(frameGeo, frameMat);
    frame.position.z = 0.001;
    this._dopplerGroup.add(frame);

    // Title label
    const titleSprite = this._createHoloLabel('DOPPLER SPECTRUM', 0x5588cc);
    titleSprite.position.set(0, panelH / 2 + 0.12, 0);
    titleSprite.scale.set(1.1, 0.18, 1);
    this._dopplerGroup.add(titleSprite);

    // Axis labels
    const xLabel = this._createHoloLabel('FREQUENCY BIN', 0x446688);
    xLabel.position.set(0, -panelH / 2 - 0.1, 0);
    xLabel.scale.set(0.9, 0.13, 1);
    this._dopplerGroup.add(xLabel);

    const yLabel = this._createHoloLabel('MAG', 0x446688);
    yLabel.position.set(-panelW / 2 - 0.15, 0, 0);
    yLabel.scale.set(0.35, 0.13, 1);
    this._dopplerGroup.add(yLabel);

    this._scene.add(this._dopplerGroup);

    // Smoothed bin values for animation
    this._dopplerBins = new Float32Array(16);
  }

  _updateDopplerSpectrumPanel(data, elapsed) {
    if (!this._dopplerGroup) return;

    const ctx = this._dopplerCtx;
    const W = 256;
    const H = 128;
    const N_BINS = 16;

    // Clear
    ctx.fillStyle = 'rgba(0, 0, 17, 1)';
    ctx.fillRect(0, 0, W, H);

    // Generate Doppler spectrum from scene data
    const feat = data?.features || {};
    const motionPower = feat.motion_band_power || 0;
    const dominantFreq = feat.dominant_freq_hz || 0;
    const spectralPower = feat.spectral_power || 0;

    // Synthesize 16 frequency bins spanning 0-10 Hz (Nyquist for 20 Hz sample rate)
    const targetBins = new Float32Array(N_BINS);
    for (let b = 0; b < N_BINS; b++) {
      const binFreq = (b + 0.5) * (10.0 / N_BINS); // center frequency of bin
      // Create spectral shape: peaked around dominant frequency + noise floor
      const distFromPeak = Math.abs(binFreq - dominantFreq * 10);
      const peakContrib = Math.exp(-distFromPeak * distFromPeak * 0.15) * motionPower;
      const noise = Math.random() * 0.04;
      const breathingBump = binFreq < 1.0 ? (feat.breathing_band_power || 0) * 0.5 : 0;
      targetBins[b] = Math.min(1.0, peakContrib + breathingBump + spectralPower * 0.08 + noise);
    }

    // Smooth transition (exponential moving average)
    for (let b = 0; b < N_BINS; b++) {
      this._dopplerBins[b] += (targetBins[b] - this._dopplerBins[b]) * 0.15;
    }

    // Draw bars with blue-to-red gradient
    const barW = (W - 16) / N_BINS; // leave margin
    const margin = 8;

    for (let b = 0; b < N_BINS; b++) {
      const val = this._dopplerBins[b];
      const barH = Math.max(2, val * (H - 16));
      const x = margin + b * barW;
      const y = H - 4 - barH;

      // Color: blue(low freq) -> cyan -> green -> yellow -> red(high freq/magnitude)
      // Blend by both bin position and magnitude
      const t = val; // magnitude-based color
      const hue = 0.6 - t * 0.6; // 0.6=blue -> 0=red
      const sat = 0.85 + val * 0.15;
      const light = 0.12 + val * 0.48;

      // Bar fill
      ctx.fillStyle = `hsl(${Math.round(hue * 360)}, ${Math.round(sat * 100)}%, ${Math.round(light * 100)}%)`;
      ctx.fillRect(x + 1, y, barW - 2, barH);

      // Glow effect at top of bar
      const glowAlpha = Math.min(0.6, val * 0.8);
      ctx.fillStyle = `hsla(${Math.round(hue * 360)}, 100%, 70%, ${glowAlpha})`;
      ctx.fillRect(x + 1, y, barW - 2, Math.min(4, barH));
    }

    // Draw baseline
    ctx.strokeStyle = 'rgba(32, 144, 255, 0.3)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margin, H - 4);
    ctx.lineTo(W - margin, H - 4);
    ctx.stroke();

    this._dopplerTexture.needsUpdate = true;

    // Subtle float animation
    this._dopplerGroup.position.y = 1.4 + Math.sin(elapsed * 0.7 + 2.0) * 0.04;
  }

  // ========================================
  // SIGNAL FIELD FLOOR (Gaussian Splat-like)
  // ========================================

  _buildSignalFieldFloor() {
    // 20x20 grid rendered as InstancedMesh with a single shared material
    // and per-instance color via InstancedBufferAttribute (P1-7 fix:
    // replaces 400 individual MeshBasicMaterials with one).
    const gridSize = 20;
    const count = gridSize * gridSize;
    this._floorFieldCount = count;

    const sphereGeo = new THREE.SphereGeometry(0.08, 8, 8);
    this._floorMaterial = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this._floorInstancedMesh = new THREE.InstancedMesh(sphereGeo, this._floorMaterial, count);
    this._floorInstancedMesh.name = 'signal-field-floor';
    this._floorInstancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    // Per-instance color buffer
    const colorArray = new Float32Array(count * 3);
    this._floorInstancedMesh.instanceColor = new THREE.InstancedBufferAttribute(colorArray, 3);
    this._floorInstancedMesh.instanceColor.setUsage(THREE.DynamicDrawUsage);

    // Set initial transforms and colors
    const dummy = new THREE.Object3D();
    for (let iz = 0; iz < gridSize; iz++) {
      for (let ix = 0; ix < gridSize; ix++) {
        const idx = iz * gridSize + ix;
        dummy.position.set(
          (ix - gridSize / 2) * 0.6 + 0.3,
          0.04,
          (iz - gridSize / 2) * 0.5 + 0.25
        );
        dummy.scale.setScalar(1);
        dummy.updateMatrix();
        this._floorInstancedMesh.setMatrixAt(idx, dummy.matrix);
        // Default dim blue
        colorArray[idx * 3] = 0.04;
        colorArray[idx * 3 + 1] = 0.08;
        colorArray[idx * 3 + 2] = 0.16;
      }
    }
    this._floorInstancedMesh.instanceMatrix.needsUpdate = true;
    this._floorInstancedMesh.instanceColor.needsUpdate = true;

    this._scene.add(this._floorInstancedMesh);

    // Reusable Object3D for per-frame matrix updates
    this._floorDummy = new THREE.Object3D();
    // Store base positions for Y-offset animation
    this._floorBasePositions = new Float32Array(count * 3);
    for (let iz = 0; iz < gridSize; iz++) {
      for (let ix = 0; ix < gridSize; ix++) {
        const idx = iz * gridSize + ix;
        this._floorBasePositions[idx * 3] = (ix - gridSize / 2) * 0.6 + 0.3;
        this._floorBasePositions[idx * 3 + 1] = 0.04;
        this._floorBasePositions[idx * 3 + 2] = (iz - gridSize / 2) * 0.5 + 0.25;
      }
    }
  }

  _updateSignalFieldFloor(data, elapsed) {
    if (!this._floorInstancedMesh) return;
    const field = data?.signal_field?.values;
    const motionPower = data?.features?.motion_band_power || 0;
    const count = this._floorFieldCount;
    const colors = this._floorInstancedMesh.instanceColor.array;
    const dummy = this._floorDummy;
    const basePos = this._floorBasePositions;
    const gridSize = 20;

    // Build per-zone presence counts for coloring
    // Zones map to grid quadrants: 1001=NW, 1002=NE, 1003=SW, 1004=SE
    const zones = this._liveState?.zones || [];
    const zonePresence = [0, 0, 0, 0]; // indices 0-3 for rooms 1001-1004
    if (zones.length > 0) {
      // Use live zone data if available
      for (let z = 0; z < Math.min(zones.length, 4); z++) {
        zonePresence[z] = zones[z]?.presenceCount || 0;
      }
    } else {
      // Distribute estimated_persons across zones for demo mode
      const totalPersons = data?.estimated_persons || 0;
      if (totalPersons > 0) zonePresence[0] = Math.min(totalPersons, 2);
      if (totalPersons > 2) zonePresence[1] = totalPersons - 2;
    }

    for (let i = 0; i < count; i++) {
      const ix = i % gridSize;
      const iz = Math.floor(i / gridSize);

      // Determine which zone this grid cell belongs to
      // ix < 10 = west, ix >= 10 = east; iz < 10 = north, iz >= 10 = south
      const zoneIdx = (ix < 10 ? 0 : 1) + (iz < 10 ? 0 : 2);
      const presence = zonePresence[zoneIdx];

      // Use signal field data if available, otherwise generate from features
      const v = field ? (field[i] || 0) : 0.05;

      // Color: modulate by zone presence count
      // Base: blue(quiet) -> cyan -> green -> yellow -> red(active)
      // Presence adds warmth: 0=blue tint, 1+=cyan/green, 2+=amber
      let r, g, b;
      if (presence === 0) {
        // No presence: cool blue tones
        if (v < 0.5) {
          const t = v * 2;
          r = 0; g = t * 0.3; b = 0.3 + t * 0.5;
        } else {
          const t = (v - 0.5) * 2;
          r = 0; g = 0.3 + t * 0.3; b = 0.8 - t * 0.3;
        }
      } else if (presence === 1) {
        // Single presence: cyan/green
        if (v < 0.5) {
          const t = v * 2;
          r = 0; g = t; b = 1 - t * 0.5;
        } else {
          const t = (v - 0.5) * 2;
          r = t * 0.3; g = 1 - t * 0.3; b = 0.5 - t * 0.3;
        }
      } else {
        // Multiple presence: warm amber/green
        if (v < 0.5) {
          const t = v * 2;
          r = t * 0.6; g = t * 0.8; b = 0.1;
        } else {
          const t = (v - 0.5) * 2;
          r = 0.6 + t * 0.4; g = 0.8 - t * 0.3; b = 0.1;
        }
      }
      colors[i * 3] = r;
      colors[i * 3 + 1] = g;
      colors[i * 3 + 2] = b;

      // Pulsate scale based on motion energy
      const pulseFactor = 1 + Math.sin(elapsed * 2.5 + i * 0.15) * motionPower * 0.6;
      const baseScale = 0.6 + v * 1.8;

      // Y-offset pulsation for active areas
      dummy.position.set(
        basePos[i * 3],
        basePos[i * 3 + 1] + v * Math.sin(elapsed * 1.8 + i * 0.1) * 0.03,
        basePos[i * 3 + 2]
      );
      dummy.scale.setScalar(baseScale * pulseFactor);
      dummy.updateMatrix();
      this._floorInstancedMesh.setMatrixAt(i, dummy.matrix);
    }

    this._floorInstancedMesh.instanceMatrix.needsUpdate = true;
    this._floorInstancedMesh.instanceColor.needsUpdate = true;
    // Adjust shared material opacity based on average signal level
    this._floorMaterial.opacity = 0.35;
  }

  // ========================================
  // VITALS ORACLE
  // ========================================

  _buildVitalsOracle() {
    this._vitalsOracleGroup = new THREE.Group();
    this._vitalsOracleGroup.name = 'vitals-oracle';
    this._vitalsOracleGroup.position.set(4.5, 2.5, -2);

    // Breathing ring — violet torus
    const breathGeo = new THREE.TorusGeometry(0.5, 0.03, 16, 64);
    this._voBreathMat = new THREE.MeshBasicMaterial({
      color: 0x8844ff,
      transparent: true,
      opacity: 0.7,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this._voBreathRing = new THREE.Mesh(breathGeo, this._voBreathMat);
    this._voBreathRing.rotation.x = Math.PI * 0.4;
    this._vitalsOracleGroup.add(this._voBreathRing);

    // Heart rate ring — crimson torus, rotated 90 degrees
    const hrGeo = new THREE.TorusGeometry(0.35, 0.025, 16, 64);
    this._voHrMat = new THREE.MeshBasicMaterial({
      color: 0xff2244,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this._voHrRing = new THREE.Mesh(hrGeo, this._voHrMat);
    this._voHrRing.rotation.x = Math.PI * 0.5;
    this._voHrRing.rotation.z = Math.PI * 0.15;
    this._vitalsOracleGroup.add(this._voHrRing);

    // Center orb with emissive glow
    const orbGeo = new THREE.SphereGeometry(0.12, 24, 24);
    this._voOrbMat = new THREE.MeshBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending,
    });
    this._voOrb = new THREE.Mesh(orbGeo, this._voOrbMat);
    this._vitalsOracleGroup.add(this._voOrb);

    // Point light for bloom effect
    this._voLight = new THREE.PointLight(0x00d4ff, 1.5, 6);
    this._vitalsOracleGroup.add(this._voLight);

    // Title label
    const titleSprite = this._createHoloLabel('VITAL SIGNS', 0x8866cc);
    titleSprite.position.set(0, 0.8, 0);
    titleSprite.scale.set(1.0, 0.18, 1);
    this._vitalsOracleGroup.add(titleSprite);

    this._scene.add(this._vitalsOracleGroup);
  }

  _updateVitalsOracle(data, elapsed) {
    if (!this._vitalsOracleGroup) return;

    const vs = data?.vital_signs || {};
    const breathBpm = vs.breathing_rate_bpm || 0;
    const hrBpm = vs.heart_rate_bpm || 0;
    const breathConf = vs.breathing_confidence || 0;
    const hrConf = vs.heart_rate_confidence || 0;

    // Breathing ring pulsation at breathing_rate_bpm frequency
    const breathFreq = breathBpm / 60;
    const breathPulse = breathFreq > 0 ? Math.sin(elapsed * Math.PI * 2 * breathFreq) : 0;
    const breathScale = 1.0 + breathPulse * 0.08 * breathConf;
    this._voBreathRing.scale.set(breathScale, breathScale, 1);
    this._voBreathMat.opacity = 0.3 + breathConf * 0.5;

    // Heart ring pulsation — double-peak lub-dub pattern
    const hrFreq = hrBpm / 60;
    let hrPulse = 0;
    if (hrFreq > 0) {
      const phase = (elapsed * hrFreq) % 1.0;
      // Lub-dub: two peaks per beat cycle at phase 0.0 and 0.15
      const lub = Math.exp(-Math.pow((phase - 0.0) * 8, 2));
      const dub = Math.exp(-Math.pow((phase - 0.15) * 10, 2)) * 0.7;
      hrPulse = lub + dub;
    }
    const hrScale = 1.0 + hrPulse * 0.1 * hrConf;
    this._voHrRing.scale.set(hrScale, hrScale, 1);
    this._voHrMat.opacity = 0.2 + hrConf * 0.5;

    // Slow rotation for both rings
    this._voBreathRing.rotation.z = elapsed * 0.1;
    this._voHrRing.rotation.z = -elapsed * 0.15;

    // Center orb color shift based on confidence (blue -> green -> white)
    const avgConf = (breathConf + hrConf) * 0.5;
    const orbColor = new THREE.Color();
    if (avgConf < 0.5) {
      // Blue to green
      orbColor.setRGB(0, avgConf * 2, 1.0 - avgConf);
    } else {
      // Green to white
      const t = (avgConf - 0.5) * 2;
      orbColor.setRGB(t, 1.0, t);
    }
    this._voOrbMat.color.copy(orbColor);
    this._voLight.color.copy(orbColor);

    // Orb scale pulsates with breathing
    const orbPulse = 1.0 + breathPulse * 0.1;
    this._voOrb.scale.set(orbPulse, orbPulse, orbPulse);
    this._voLight.intensity = 0.8 + Math.abs(breathPulse) * 1.0;

    // Subtle float animation
    this._vitalsOracleGroup.position.y = 2.5 + Math.sin(elapsed * 0.5) * 0.05;
  }

  // ========================================
  // PHASE CONSTELLATION
  // ========================================

  _buildPhaseConstellation() {
    const NUM_POINTS = 30;
    this._pcNumPoints = NUM_POINTS;

    this._pcGroup = new THREE.Group();
    this._pcGroup.name = 'phase-constellation';
    this._pcGroup.position.set(4.5, 1.0, -2);

    // Background reference circle ring
    const ringGeo = new THREE.TorusGeometry(0.6, 0.005, 8, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0.15,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    this._pcGroup.add(ring);

    // Constellation star points
    const starGeo = new THREE.BufferGeometry();
    this._pcPositions = new Float32Array(NUM_POINTS * 3);
    this._pcColors = new Float32Array(NUM_POINTS * 3);
    this._pcSizes = new Float32Array(NUM_POINTS);

    // Initialize points in a circle
    for (let i = 0; i < NUM_POINTS; i++) {
      const angle = (i / NUM_POINTS) * Math.PI * 2;
      this._pcPositions[i * 3] = Math.cos(angle) * 0.5;
      this._pcPositions[i * 3 + 1] = Math.sin(angle) * 0.5;
      this._pcPositions[i * 3 + 2] = 0;
      this._pcColors[i * 3] = 0;
      this._pcColors[i * 3 + 1] = 0.5;
      this._pcColors[i * 3 + 2] = 1.0;
      this._pcSizes[i] = 0.06;
    }

    starGeo.setAttribute('position', new THREE.BufferAttribute(this._pcPositions, 3));
    starGeo.setAttribute('color', new THREE.BufferAttribute(this._pcColors, 3));
    starGeo.setAttribute('size', new THREE.BufferAttribute(this._pcSizes, 1));

    const starMat = new THREE.PointsMaterial({
      size: 0.08,
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    });
    this._pcStars = new THREE.Points(starGeo, starMat);
    this._pcGroup.add(this._pcStars);

    // Title label
    const titleSprite = this._createHoloLabel('PHASE CONSTELLATION', 0x5588cc);
    titleSprite.position.set(0, 0.9, 0);
    titleSprite.scale.set(1.2, 0.18, 1);
    this._pcGroup.add(titleSprite);

    this._scene.add(this._pcGroup);
  }

  _updatePhaseConstellation(data, elapsed) {
    if (!this._pcGroup) return;

    const NUM_POINTS = this._pcNumPoints;
    const feat = data?.features || {};
    const variance = feat.variance || 0;
    const motionPower = feat.motion_band_power || 0;

    // Slow Y rotation for temporal evolution
    this._pcGroup.rotation.y = elapsed * 0.05;

    for (let i = 0; i < NUM_POINTS; i++) {
      // Each point represents a subcarrier's phase angle on the constellation
      const baseAngle = (i / NUM_POINTS) * Math.PI * 2;
      const phaseShift = Math.sin(elapsed * 0.8 + i * 0.35) * variance * 1.5;
      const angle = baseAngle + phaseShift;

      // Amplitude determines radius (dim = close to center, bright = outer)
      const amp = 0.3 + Math.sin(elapsed * 1.2 + i * 0.5) * 0.15 + motionPower * 0.2;
      const radius = 0.2 + amp * 0.5;

      this._pcPositions[i * 3] = Math.cos(angle) * radius;
      this._pcPositions[i * 3 + 1] = Math.sin(angle) * radius;
      this._pcPositions[i * 3 + 2] = 0;

      // Color based on amplitude (dim blue -> bright cyan/white)
      const brightness = Math.min(1.0, amp * 1.5);
      this._pcColors[i * 3] = brightness * 0.4;
      this._pcColors[i * 3 + 1] = 0.3 + brightness * 0.7;
      this._pcColors[i * 3 + 2] = 0.6 + brightness * 0.4;

      // Size based on variance (stable = small, active = large)
      const varFactor = Math.abs(Math.sin(elapsed * 1.5 + i * 0.7)) * variance;
      this._pcSizes[i] = 0.04 + varFactor * 0.12;
    }

    this._pcStars.geometry.attributes.position.needsUpdate = true;
    this._pcStars.geometry.attributes.color.needsUpdate = true;
    this._pcStars.geometry.attributes.size.needsUpdate = true;

    // Subtle float animation
    this._pcGroup.position.y = 1.0 + Math.sin(elapsed * 0.6 + 1.5) * 0.04;
  }

  // ========================================
  // PRESENCE CARTOGRAPHY — Zone Enhancements
  // ========================================

  _enhanceSignalFieldFloorZones() {
    // Zone boundary outlines and labels for rooms 1001-1004
    // The floor grid is 20x20 spanning roughly -6..+6 (X) x -5..+5 (Z)
    // Divide into 4 quadrants for 4 rooms
    this._zoneGroup = new THREE.Group();
    this._zoneGroup.name = 'presence-zones';

    const zones = [
      { id: '1001', cx: -3, cz: -2.5, w: 5.5, d: 4.5 },
      { id: '1002', cx: 3,  cz: -2.5, w: 5.5, d: 4.5 },
      { id: '1003', cx: -3, cz: 2.5,  w: 5.5, d: 4.5 },
      { id: '1004', cx: 3,  cz: 2.5,  w: 5.5, d: 4.5 },
    ];
    this._zoneDefinitions = zones;

    const lineMat = new THREE.LineBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0.25,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    for (const zone of zones) {
      // Zone boundary outline (rectangle on the floor)
      const hw = zone.w / 2;
      const hd = zone.d / 2;
      const points = [
        new THREE.Vector3(zone.cx - hw, 0.06, zone.cz - hd),
        new THREE.Vector3(zone.cx + hw, 0.06, zone.cz - hd),
        new THREE.Vector3(zone.cx + hw, 0.06, zone.cz + hd),
        new THREE.Vector3(zone.cx - hw, 0.06, zone.cz + hd),
        new THREE.Vector3(zone.cx - hw, 0.06, zone.cz - hd),
      ];
      const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
      const outline = new THREE.Line(lineGeo, lineMat);
      this._zoneGroup.add(outline);

      // Floating text label above each zone
      const label = this._createHoloLabel(zone.id, 0x00d4ff);
      label.position.set(zone.cx, 0.35, zone.cz);
      label.scale.set(0.8, 0.16, 1);
      this._zoneGroup.add(label);
    }

    this._scene.add(this._zoneGroup);
  }

  // ---- FPS ----

  _updateFPS(dt) {
    this._fpsFrames++;
    this._fpsTime += dt;
    if (this._fpsTime >= 1) {
      this._fpsValue = Math.round(this._fpsFrames / this._fpsTime);
      this._fpsFrames = 0;
      this._fpsTime = 0;
      if (this._showFps) {
        document.getElementById('fps-counter').textContent = `${this._fpsValue} FPS`;
      }
      this._adaptQuality();
    }
  }

  _adaptQuality() {
    let nl = this._qualityLevel;
    if (this._fpsValue < 25 && nl > 0) nl--;
    else if (this._fpsValue > 55 && nl < 2) nl++;
    if (nl !== this._qualityLevel) {
      this._qualityLevel = nl;
      this._nebula.setQuality(nl);
      this._postProcessing.setQuality(nl);
    }
  }

  _onResize() {
    const w = window.innerWidth, h = window.innerHeight;
    this._camera.aspect = w / h;
    this._camera.updateProjectionMatrix();
    this._renderer.setSize(w, h);
    this._postProcessing.resize(w, h);
  }
}

new Observatory();
