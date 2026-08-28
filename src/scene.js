import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// The model is built in millimetres and centred on the dental content, so its
// extent is roughly 100mm across. Camera distances below are in the same units.
const FRAME_DISTANCE = 230;
const FLY_MS = 620;

const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function createScene(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x14161a);

  // RoomEnvironment gives soft studio image-based lighting with no HDRI file to
  // ship — important for keeping the payload down when the mesh is already 6MB.
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.position.set(0.4, 0.8, 1);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, 0.5);
  fill.position.set(-0.6, 0.2, -0.8);
  scene.add(fill);

  const camera = new THREE.PerspectiveCamera(42, 1, 1, 5000);
  camera.position.set(0, 10, FRAME_DISTANCE);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 45;
  controls.maxDistance = 900;
  controls.target.set(0, 0, 0);

  const root = new THREE.Group();
  scene.add(root);

  function resize() {
    const { clientWidth: w, clientHeight: h } = canvas;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(canvas);
  resize();

  // --- camera flight -------------------------------------------------------
  let flight = null;

  function flyTo(focus, distance) {
    // Approach from the current viewing direction so the model never appears to
    // spin under the user; only the framing changes.
    const dir = camera.position.clone().sub(controls.target).normalize();
    flight = {
      t: 0,
      fromPos: camera.position.clone(),
      fromTarget: controls.target.clone(),
      toPos: focus.clone().add(dir.multiplyScalar(distance)),
      toTarget: focus.clone(),
    };
  }

  function resetView() {
    flight = {
      t: 0,
      fromPos: camera.position.clone(),
      fromTarget: controls.target.clone(),
      toPos: new THREE.Vector3(0, 10, FRAME_DISTANCE),
      toTarget: new THREE.Vector3(0, 0, 0),
    };
  }

  let last = performance.now();
  function tick(now) {
    const dt = now - last;
    last = now;

    if (flight) {
      flight.t = Math.min(1, flight.t + dt / FLY_MS);
      const k = easeInOut(flight.t);
      camera.position.lerpVectors(flight.fromPos, flight.toPos, k);
      controls.target.lerpVectors(flight.fromTarget, flight.toTarget, k);
      if (flight.t >= 1) flight = null;
    }

    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  async function load(url) {
    const gltf = await new GLTFLoader().loadAsync(url);
    const meshes = new Map();

    gltf.scene.traverse((obj) => {
      if (!obj.isMesh) return;
      // Node names are FMA ids, set by tools/build-assets.mjs. Clone the material
      // per mesh so hover and selection can tint one structure without touching
      // every other structure sharing that layer's material.
      obj.material = obj.material.clone();
      obj.material.transparent = true;
      obj.userData.baseColor = obj.material.color.clone();
      meshes.set(obj.name, obj);
    });

    root.add(gltf.scene);
    return meshes;
  }

  return { scene, camera, controls, renderer, root, load, flyTo, resetView };
}
