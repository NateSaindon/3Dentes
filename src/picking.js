import * as THREE from 'three';

// Distinguish a click from the end of an orbit drag. Without this every rotation
// that happens to finish over a tooth would select it.
const DRAG_SLOP_PX = 6;

// A structure you can see straight through should not intercept clicks meant for
// what is behind it: with gingiva at its default 45%, the posterior teeth are
// plainly visible but every click on one would otherwise select the gingiva.
// Above this opacity a structure reads as solid and does absorb the click, so
// turning gingiva up to full opacity makes it selectable again.
const SOLID_OPACITY = 0.6;

export function createPicking(canvas, camera, root, { onHover, onSelect }) {
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let downAt = null;
  let hovered = null;

  function pick(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);

    // Only visible meshes are candidates, so a hidden layer can't be picked
    // through whatever is drawn in front of it.
    const hits = raycaster.intersectObject(root, true)
      .filter((h) => h.object.isMesh && h.object.visible && h.object.material.opacity > 0.05);
    if (!hits.length) return null;

    // Prefer the nearest solid structure, so see-through tissue in front of a
    // tooth doesn't steal the click. If everything on the ray is see-through,
    // the nearest one is genuinely what was clicked.
    const solid = hits.find((h) => h.object.material.opacity >= SOLID_OPACITY);
    return (solid ?? hits[0]).object;
  }

  canvas.addEventListener('pointermove', (e) => {
    if (e.pointerType === 'touch') return; // no hover state on touch
    const hit = pick(e.clientX, e.clientY);
    if (hit !== hovered) {
      hovered = hit;
      canvas.style.cursor = hit ? 'pointer' : 'grab';
      onHover(hit ? hit.name : null);
    }
  });

  canvas.addEventListener('pointerleave', () => {
    if (hovered) { hovered = null; onHover(null); }
  });

  canvas.addEventListener('pointerdown', (e) => {
    downAt = { x: e.clientX, y: e.clientY };
  });

  canvas.addEventListener('pointerup', (e) => {
    if (!downAt) return;
    const moved = Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y);
    downAt = null;
    if (moved > DRAG_SLOP_PX) return;
    const hit = pick(e.clientX, e.clientY);
    onSelect(hit ? hit.name : null);
  });
}
