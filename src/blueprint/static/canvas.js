// Drag tables around and save the page back out with the new layout embedded.
// `edgePath` and `num` mirror render.py so redrawn edges match bp's output.
(() => {
  'use strict';
  const dataEl = document.getElementById('bp-data');
  const data = JSON.parse(dataEl.textContent);
  const G = data.geometry;
  const canvas = document.getElementById('canvas');
  const svg = document.getElementById('edges');
  const stateEl = document.getElementById('save-state');
  const tables = new Map([...canvas.querySelectorAll('.table')].map((t) => [t.dataset.name, t]));
  const edges = [...svg.querySelectorAll('.edge')];

  let pinned = Object.keys(data.layout.tables || {}).length > 0;
  let dirty = false;
  let fileHandle = null;

  // --- geometry / routing (mirrors render.py) ------------------------------
  const num = (v) => String(Math.floor(v * 10 + 0.5) / 10);

  function box(name) {
    const t = tables.get(name);
    const x = parseFloat(t.style.left);
    return { x, y: parseFloat(t.style.top), right: x + G.tableW };
  }

  function rowY(b, index) {
    if (index < 0) return b.y + G.border + G.headerH / 2;
    return b.y + G.border + G.headerH + index * G.rowH + G.rowH / 2;
  }

  function slotIndex(name, slot) {
    const rows = [...tables.get(name).querySelectorAll('.row[data-slot]')];
    return rows.findIndex((r) => r.dataset.slot === slot);
  }

  function edgePath(src, sy, dst, ty, waypoints) {
    if (!waypoints.length && dst.x < src.right && src.x < dst.right) {
      const sx = src.right, tx = dst.right, bulge = G.loop + Math.abs(ty - sy) / 6;
      const d = `M${num(sx)},${num(sy)} C${num(sx + bulge)},${num(sy)} ${num(tx + bulge)},${num(ty)} ${num(tx)},${num(ty)}`;
      return [d, [Math.max(sx, tx) + bulge * 0.75, (sy + ty) / 2]];
    }
    const forward = dst.x > src.x;
    const [sx, tx] = forward ? [src.right, dst.x] : [src.x, dst.right];
    const anchors = [[sx, sy], ...waypoints, [tx, ty]];
    let d = `M${num(sx)},${num(sy)}`;
    for (let j = 1; j < anchors.length; j++) {
      const [ax, ay] = anchors[j - 1], [bx, by] = anchors[j];
      if (j % 2) {
        const mx = (ax + bx) / 2;
        d += ` C${num(mx)},${num(ay)} ${num(mx)},${num(by)} ${num(bx)},${num(by)}`;
      } else {
        d += ` L${num(bx)},${num(by)}`;
      }
    }
    const [ax, ay] = anchors[0], [bx, by] = anchors[1];
    return [d, [(ax + bx) / 2, (ay + by) / 2]];
  }

  function waypointsOf(edge) {
    return edge.dataset.waypoints ? JSON.parse(edge.dataset.waypoints) : [];
  }

  function redraw(edge) {
    const { from, fromSlot, to, toSlot } = edge.dataset;
    const src = box(from), dst = box(to);
    const sy = rowY(src, slotIndex(from, fromSlot));
    const ty = rowY(dst, toSlot ? slotIndex(to, toSlot) : -1);
    const [d, [lx, ly]] = edgePath(src, sy, dst, ty, waypointsOf(edge));
    edge.querySelector('path').setAttribute('d', d);
    const label = edge.querySelector('text');
    label.setAttribute('x', num(lx));
    label.setAttribute('y', num(ly));
  }

  function fitCanvas() {
    let w = 0, h = 0;
    for (const t of tables.values()) {
      w = Math.max(w, parseFloat(t.style.left) + G.tableW);
      h = Math.max(h, parseFloat(t.style.top) + t.offsetHeight);
    }
    for (const e of edges) {
      const b = e.getBBox();
      w = Math.max(w, b.x + b.width);
      h = Math.max(h, b.y + b.height);
    }
    w = Math.ceil(w + G.pad), h = Math.ceil(h + G.pad);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    svg.setAttribute('width', w);
    svg.setAttribute('height', h);
  }

  function setState(cls, text) {
    if (!stateEl) return;
    stateEl.className = `save-state ${cls}`;
    stateEl.textContent = text;
  }

  function markDirty() {
    dirty = true;
    setState('', 'unsaved changes');
  }

  // --- dragging ------------------------------------------------------------
  canvas.classList.add('draggable');
  for (const [name, t] of tables) {
    t.addEventListener('pointerdown', (ev) => {
      if (ev.button !== 0) return;
      ev.preventDefault();
      t.setPointerCapture(ev.pointerId);
      t.classList.add('dragging');
      const start = { x: ev.clientX, y: ev.clientY, left: box(name).x, top: box(name).y };
      const attached = edges.filter((e) => e.dataset.from === name || e.dataset.to === name);
      let moved = false;

      const move = (e) => {
        const left = Math.max(0, Math.round(start.left + e.clientX - start.x));
        const top = Math.max(0, Math.round(start.top + e.clientY - start.y));
        if (!moved && left === start.left && top === start.top) return;
        moved = true;
        t.style.left = `${left}px`;
        t.style.top = `${top}px`;
        for (const edge of attached) {
          delete edge.dataset.waypoints; // lanes belonged to the old position
          redraw(edge);
        }
      };
      const end = () => {
        t.removeEventListener('pointermove', move);
        t.classList.remove('dragging');
        if (!moved) return;
        pinned = true;
        fitCanvas();
        markDirty();
      };
      t.addEventListener('pointermove', move);
      t.addEventListener('pointerup', end, { once: true });
      t.addEventListener('pointercancel', end, { once: true });
    });
  }

  // --- reset / save ----------------------------------------------------------
  function resetLayout() {
    for (const [name, pos] of Object.entries(data.auto.tables)) {
      const t = tables.get(name);
      if (!t) continue;
      t.style.left = `${num(pos.x)}px`;
      t.style.top = `${num(pos.y)}px`;
    }
    for (const edge of edges) {
      const pts = data.auto.edges[edge.dataset.id];
      if (pts) edge.dataset.waypoints = JSON.stringify(pts);
      else delete edge.dataset.waypoints;
      redraw(edge);
    }
    pinned = false;
    fitCanvas();
    markDirty();
  }

  function currentLayout() {
    if (!pinned) return {};
    const layout = { tables: {}, edges: {} };
    for (const name of tables.keys()) {
      const b = box(name);
      layout.tables[name] = { x: b.x, y: b.y };
    }
    for (const edge of edges) {
      const pts = waypointsOf(edge);
      if (pts.length) layout.edges[edge.dataset.id] = pts;
    }
    return layout;
  }

  async function save() {
    data.layout = currentLayout();
    dataEl.textContent = JSON.stringify(data).replaceAll('</', '<\\/');
    setState('', '');
    const html = '<!doctype html>\n' + document.documentElement.outerHTML + '\n';
    const name = data.file || 'blueprint.html';
    try {
      if (window.showSaveFilePicker) {
        fileHandle ??= await window.showSaveFilePicker({
          suggestedName: name,
          types: [{ description: 'HTML', accept: { 'text/html': ['.html'] } }]
        });
        const w = await fileHandle.createWritable();
        await w.write(html);
        await w.close();
        setState('saved', `saved ✓ ${fileHandle.name}`);
      } else {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
        a.download = name;
        a.click();
        URL.revokeObjectURL(a.href);
        setState('saved', `downloaded ${name} — replace the original with it`);
      }
      dirty = false;
    } catch (err) {
      if (err.name === 'AbortError') return setState('', dirty ? 'unsaved changes' : '');
      setState('error', `save failed: ${err.message}`);
    }
  }

  document.getElementById('actions').hidden = false;
  document.getElementById('save').addEventListener('click', save);
  document.getElementById('reset').addEventListener('click', resetLayout);
  window.addEventListener('beforeunload', (e) => {
    if (dirty) e.preventDefault();
  });

  const panel = document.getElementById('panel');
  const toggle = document.getElementById('toggle-panel');
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    panel.classList.toggle('open');
    toggle.textContent = panel.classList.contains('open') ? '◀' : '▶';
  });
})();
