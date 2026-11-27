(async () => {
  const LEVELS = [10.5, 11.5, 12, 12.5, 13, 13.5];  // remove some to capture faster / use less memory
  const MARGIN_PX = 1500;     // extra map around the outermost markers, in image pixels
  const MAX_PIXELS = 150e6;   // largest image to build (13.5 gets less margin to stay under this)
  const HIDE = /marker|location|cluster|heatmap/i;  // map layers matching this are hidden while capturing

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const lats = mapData.locations.map(l => l.latitude);
  const lngs = mapData.locations.map(l => l.longitude);
  const BASE = 0.03;
  const nw0 = mapboxgl.MercatorCoordinate.fromLngLat([Math.min(...lngs) - BASE, Math.max(...lats) + BASE]);
  const se0 = mapboxgl.MercatorCoordinate.fromLngLat([Math.max(...lngs) + BASE, Math.min(...lats) - BASE]);

  const oldMaxBounds = map.getMaxBounds();
  const oldMin = map.getMinZoom(), oldMax = map.getMaxZoom();
  map.setMaxBounds(null); map.setMinZoom(0); map.setMaxZoom(22);
  map.setBearing(0); map.setPitch(0);

  const layers = map.getStyle().layers;
  console.log('map layers:', layers.map(l => l.id).join(', '));
  const hidden = [];
  for (const l of layers) {
    if (HIDE.test(l.id) && map.getLayoutProperty(l.id, 'visibility') !== 'none') {
      map.setLayoutProperty(l.id, 'visibility', 'none'); hidden.push(l.id);
    }
  }
  console.log('hidden while capturing:', hidden.join(', ') || '(none matched)');

  const cv = map.getCanvas();
  const cw = cv.width, ch = cv.height;
  const dpr = cw / cv.clientWidth;
  const meta = { dpr, levels: [] };
  const save = (name, blob) => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name; a.click();
  };

  try {
    for (const z of LEVELS) {
      const S = 512 * Math.pow(2, z) * dpr;
      const w0 = (se0.x - nw0.x) * S, h0 = (se0.y - nw0.y) * S;
      let m = MARGIN_PX;
      if ((w0 + 2 * m) * (h0 + 2 * m) > MAX_PIXELS) {
        const b = w0 + h0, c = w0 * h0 - MAX_PIXELS;
        m = Math.max(0, (-b + Math.sqrt(b * b - 4 * c)) / 4);
      }
      const ox = nw0.x * S - m, oy = nw0.y * S - m;
      const W = Math.ceil(w0 + 2 * m), H = Math.ceil(h0 + 2 * m);
      const big = document.createElement('canvas');
      big.width = W; big.height = H;
      const ctx = big.getContext('2d');
      const stepX = cw * 0.9, stepY = ch * 0.9;
      let n = 0, misplaced = 0;
      for (let dy = 0; dy < H; dy += stepY) {
        for (let dx = 0; dx < W; dx += stepX) {
          const cx = ox + dx + cw / 2, cy = oy + dy + ch / 2;
          const c = new mapboxgl.MercatorCoordinate(cx / S, cy / S, 0).toLngLat();
          map.jumpTo({ center: c, zoom: z });
          if (Math.abs(map.getZoom() - z) > 1e-6) throw new Error(`map would not go to zoom ${z} (got ${map.getZoom()})`);
          const mc = mapboxgl.MercatorCoordinate.fromLngLat(map.getCenter());
          if (Math.hypot(mc.x * S - cx, mc.y * S - cy) > 2) misplaced++;
          await Promise.race([new Promise(r => map.once('idle', r)), sleep(8000)]);
          await sleep(150);
          await new Promise(r => {
            map.once('render', () => { ctx.drawImage(cv, dx, dy); r(); });
            map.triggerRepaint();
          });
          n++;
        }
      }
      console.log(`zoom ${z}: ${n} tiles, ${W}x${H}, margin ${Math.round(m)}px` +
                  (misplaced ? `  WARNING: ${misplaced} tiles were not where expected` : ''));
      await new Promise(r => big.toBlob(b => { save(`ref_z${z}.png`, b); r(); }, 'image/png'));
      meta.levels.push({ zoom: z, file: `ref_z${z}.png`, S, ox, oy, W, H });
      big.width = big.height = 0;
      await sleep(1500);
    }
    save('ref_meta.json', new Blob([JSON.stringify(meta)], { type: 'application/json' }));
    console.log('done');
  } finally {
    for (const id of hidden) map.setLayoutProperty(id, 'visibility', 'visible');
    map.setMinZoom(oldMin); map.setMaxZoom(oldMax);
    if (oldMaxBounds) map.setMaxBounds(oldMaxBounds);
  }
})();
