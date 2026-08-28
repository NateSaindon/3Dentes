const NOTATIONS = [
  ['universal', 'Universal'],
  ['fdi', 'FDI'],
  ['palmer', 'Palmer'],
];

const TITLE_CASE = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/** Layer visibility + opacity controls. */
export function createLayerPanel(root, layers, { onVisibility, onOpacity }) {
  for (const [key, layer] of Object.entries(layers)) {
    const row = document.createElement('div');
    row.className = 'layer';

    const toggle = document.createElement('label');
    toggle.className = 'layer-toggle';
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = layer.visible;
    box.addEventListener('change', () => {
      onVisibility(key, box.checked);
      row.classList.toggle('is-off', !box.checked);
    });
    toggle.append(box, Object.assign(document.createElement('span'), { textContent: layer.label }));

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.className = 'layer-opacity';
    slider.min = '0.05';
    slider.max = '1';
    slider.step = '0.05';
    slider.value = String(layer.defaultOpacity);
    slider.title = `${layer.label} opacity`;
    slider.addEventListener('input', () => onOpacity(key, Number(slider.value)));

    row.append(toggle, slider);
    row.classList.toggle('is-off', !layer.visible);
    root.appendChild(row);
  }
}

/** Notation selector — which numbering system the chart and detail panel show. */
export function createNotationPicker(root, { onChange }) {
  for (const [value, label] of NOTATIONS) {
    const btn = document.createElement('button');
    btn.className = 'seg';
    btn.textContent = label;
    btn.classList.toggle('is-active', value === 'universal');
    btn.addEventListener('click', () => {
      for (const b of root.children) b.classList.remove('is-active');
      btn.classList.add('is-active');
      onChange(value);
    });
    root.appendChild(btn);
  }
}

/** Detail panel for the selected structure. */
export function createDetailPanel(root) {
  function empty() {
    root.innerHTML = '<p class="detail-empty">Select a structure in the 3D view or on the chart.</p>';
  }

  function field(label, value) {
    return `<div class="field"><dt>${label}</dt><dd>${value}</dd></div>`;
  }

  empty();

  return {
    clear: empty,
    show(s) {
      const rows = [];
      if (s.layer === 'teeth') {
        rows.push(
          field('Universal', s.universal),
          field('FDI', s.fdi),
          field('Palmer', s.palmer),
          field('Arch', TITLE_CASE(s.arch)),
          field('Quadrant', String(s.quadrant)),
        );
      }
      rows.push(field('Side', TITLE_CASE(s.side)));
      rows.push(field('FMA', s.fma.replace('FMA', '')));

      root.innerHTML = `
        <h2 class="detail-name">${s.name}</h2>
        <dl class="detail-fields">${rows.join('')}</dl>
      `;
    },
  };
}
