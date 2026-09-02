import * as THREE from 'three';
import { createScene } from './scene.js';
import { createPicking } from './picking.js';
import { createOdontogram } from './odontogram.js';
import { createLayerPanel, createNotationPicker, createDetailPanel } from './ui.js';

const HOVER_TINT = 0x2f6f8f;
const SELECT_TINT = 0x3d9bd1;

const $ = (sel) => document.querySelector(sel);

// Collapse every panel behind one button. Default to collapsed on a narrow
// screen: the panels are useful, but on a phone they cover the anatomy, and an
// atlas that opens with its subject hidden has failed before it starts.
// matchMedia is read ONCE, so a rotation or resize never yanks the panels out
// from under someone who has deliberately opened them.
//
// Wired at module scope, BEFORE the model is fetched. Inside main() it sat
// behind an await on a 9.9 MB glb, so on a slow phone connection -- precisely
// when someone wants the anatomy unobscured -- the button would not respond.
// Stamped at build time from package.json, so the corner label and the
// changelog cannot drift apart -- both move in the same commit. Wired at module
// scope like initChrome, so it does not wait on the 9.9 MB glb.
function initVersion() {
  const el = document.querySelector('#version');
  if (!el) return;
  // Guarded because this runs at MODULE SCOPE: if the build-time define ever
  // fails to substitute, a bare __APP_VERSION__ is a ReferenceError that takes
  // the whole module down with it, and the atlas would fail to load over a
  // corner label. Never worth that.
  let v = 'dev';
  try { v = __APP_VERSION__; } catch { /* define not substituted */ }
  el.textContent = v;
}

initVersion();

function initChrome() {
  const btn = document.querySelector('#chrome');
  if (!btn) return;
  const setChrome = (shown) => {
    document.body.classList.toggle('chrome-hidden', !shown);
    btn.setAttribute('aria-expanded', String(shown));
    btn.classList.toggle('is-active', !shown);
  };
  setChrome(!window.matchMedia('(max-width: 900px)').matches);
  btn.addEventListener('click', () => {
    setChrome(document.body.classList.contains('chrome-hidden'));
  });
}
initChrome();

async function main() {
  const canvas = $('#view');
  const status = $('#status');

  const meta = await fetch(`${import.meta.env.BASE_URL}teeth.json`).then((r) => r.json());
  const { layers, structures } = meta;

  const view = createScene(canvas);

  status.textContent = 'Loading anatomy…';
  const meshes = await view.load(`${import.meta.env.BASE_URL}dentition.glb`);
  status.remove();

  // --- layer state ---------------------------------------------------------
  const layerState = Object.fromEntries(
    Object.entries(layers).map(([k, l]) => [k, { visible: l.visible, opacity: l.defaultOpacity }]),
  );
  const meshesByLayer = new Map();
  for (const [fma, mesh] of meshes) {
    const layer = structures[fma]?.layer;
    if (!layer) continue;
    mesh.userData.layer = layer;
    if (!meshesByLayer.has(layer)) meshesByLayer.set(layer, []);
    meshesByLayer.get(layer).push(mesh);
  }

  let selected = null;
  let isolated = false;

  function applyLayer(key) {
    const { visible, opacity } = layerState[key];
    for (const mesh of meshesByLayer.get(key) ?? []) {
      const isFocus = isolated && selected === mesh.name;
      mesh.visible = isolated ? isFocus : visible;
      mesh.material.opacity = isFocus ? 1 : opacity;
      // A fully opaque material renders faster and avoids sort artefacts.
      mesh.material.transparent = mesh.material.opacity < 1;
      mesh.material.depthWrite = mesh.material.opacity > 0.95;
    }
  }
  const applyAll = () => Object.keys(layerState).forEach(applyLayer);

  // --- selection & highlight ----------------------------------------------
  const detail = createDetailPanel($('#detail'));
  let chart;

  function tint(fma, color) {
    const mesh = meshes.get(fma);
    if (!mesh) return;
    if (color === null) mesh.material.color.copy(mesh.userData.baseColor);
    else mesh.material.color.copy(mesh.userData.baseColor).lerp(new THREE.Color(color), 0.55);
  }

  /**
   * Where to view a structure from. Flying straight in along the current
   * direction leaves a molar hidden behind the premolars in front of it, since
   * the arch curves away from a frontal viewpoint. Approaching from outside the
   * arch — buccally — puts the camera where the tooth is actually exposed:
   * near-frontal for incisors, near-lateral for molars, and a natural
   * three-quarter view for everything between.
   */
  function approachFor(focus) {
    const outward = new THREE.Vector3(focus.x, 0, focus.z);
    if (outward.lengthSq() < 1e-6) outward.set(0, 0, 1); // dead centre: face it
    outward.normalize();
    return outward
      .add(new THREE.Vector3(0, 0, 0.32))  // bias forward, avoiding a flat profile
      .add(new THREE.Vector3(0, 0.22, 0))  // and slightly above the occlusal plane
      .normalize();
  }

  let hovered = null;
  function setHover(fma) {
    if (hovered && hovered !== selected) tint(hovered, null);
    hovered = fma;
    if (fma && fma !== selected) tint(fma, HOVER_TINT);
  }

  function select(fma, { fly = false } = {}) {
    if (selected) tint(selected, null);
    selected = fma && structures[fma] ? fma : null;

    if (selected) {
      tint(selected, SELECT_TINT);
      detail.show(structures[selected]);
      if (fly) {
        const mesh = meshes.get(selected);
        const box = new THREE.Box3().setFromObject(mesh);
        const size = box.getSize(new THREE.Vector3()).length();
        const focus = box.getCenter(new THREE.Vector3());
        view.flyTo(focus, Math.max(size * 4.2, 70), approachFor(focus));
      }
    } else {
      detail.clear();
      if (isolated) { isolated = false; $('#isolate').classList.remove('is-active'); }
    }

    chart?.setSelected(selected);
    $('#isolate').disabled = !selected;
    applyAll();
  }

  createPicking(canvas, view.camera, view.root, {
    onHover: setHover,
    onSelect: (fma) => select(fma),
  });

  // --- panels --------------------------------------------------------------
  createLayerPanel($('#layers'), layers, {
    onVisibility: (key, visible) => { layerState[key].visible = visible; applyLayer(key); },
    onOpacity: (key, opacity) => { layerState[key].opacity = opacity; applyLayer(key); },
  });

  chart = createOdontogram($('#chart'), structures, {
    onSelect: (fma) => select(fma, { fly: true }),
  });

  createNotationPicker($('#notation'), { onChange: (n) => chart.setNotation(n) });

  $('#isolate').addEventListener('click', () => {
    if (!selected) return;
    isolated = !isolated;
    $('#isolate').classList.toggle('is-active', isolated);
    applyAll();
  });

  $('#reset').addEventListener('click', () => {
    isolated = false;
    $('#isolate').classList.remove('is-active');
    select(null);
    view.resetView();
  });

  applyAll();

  // Dev-only handle so the scene can be inspected from the console or a
  // DevTools-Protocol driver. Stripped from production builds.
  if (import.meta.env.DEV) Object.assign(window, { __view: view, __meshes: meshes, __structures: structures });
}

main().catch((err) => {
  console.error(err);
  const status = document.querySelector('#status');
  if (status) status.textContent = `Failed to load: ${err.message}`;
});
