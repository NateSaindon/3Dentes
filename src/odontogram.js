// A clinical tooth chart, laid out the way a chart is always laid out: upper
// arch on top, and the PATIENT'S right on the VIEWER'S left. That matches both
// the paper convention and what you see in the 3D view, since the model puts
// anatomical right on -x.
//
// Rendered as buttons in a CSS grid rather than SVG so the cells are focusable
// and keyboard-navigable for free.

// Universal numbering, left to right as drawn:
//   upper row  1 -> 16   (upper right third molar across to upper left third molar)
//   lower row 32 -> 17   (lower right third molar across to lower left third molar)
const UPPER = Array.from({ length: 16 }, (_, i) => i + 1);
const LOWER = Array.from({ length: 16 }, (_, i) => 32 - i);

export function createOdontogram(root, structures, { onSelect }) {
  const byUniversal = new Map();
  for (const s of Object.values(structures)) {
    if (s.layer === 'teeth') byUniversal.set(Number(s.universal), s);
  }

  const cells = new Map(); // universal -> button
  let notation = 'universal';

  function buildRow(numbers, arch) {
    const row = document.createElement('div');
    row.className = 'chart-row';
    numbers.forEach((u, i) => {
      // Gap at the midline, after the 8th cell in each row.
      if (i === 8) row.appendChild(Object.assign(document.createElement('div'), { className: 'chart-gap' }));

      const s = byUniversal.get(u);
      const btn = document.createElement('button');
      btn.className = 'chart-tooth';
      btn.dataset.universal = String(u);

      if (s) {
        btn.dataset.fma = s.fma;
        btn.title = s.name;
        btn.addEventListener('click', () => onSelect(s.fma));
      } else {
        // Third molars: present as chart positions, absent from the patient.
        btn.disabled = true;
        btn.classList.add('is-absent');
        btn.title = 'Third molar — extracted, so not present in the scan';
      }
      row.appendChild(btn);
      cells.set(u, btn);
    });
    row.dataset.arch = arch;
    return row;
  }

  const chart = document.createElement('div');
  chart.className = 'chart';
  chart.append(buildRow(UPPER, 'maxillary'), buildRow(LOWER, 'mandibular'));

  const legend = document.createElement('div');
  legend.className = 'chart-legend';
  legend.innerHTML = '<span>Patient’s right</span><span>Patient’s left</span>';

  root.append(chart, legend);

  function render() {
    for (const [u, btn] of cells) {
      const s = byUniversal.get(u);
      btn.textContent = s ? s[notation] : notation === 'universal' ? String(u) : '–';
    }
  }

  render();

  return {
    setNotation(next) { notation = next; render(); },
    setSelected(fma) {
      for (const btn of cells.values()) btn.classList.toggle('is-selected', btn.dataset.fma === fma);
    },
  };
}
