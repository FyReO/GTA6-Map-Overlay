(() => {
  const WANT = [   // category groups and titles to export; edit to add or remove marker types
    { group: "Waink Locations", groupRe: /waink/i,   cats: [/landmark/i, /sculpture/i, /curio/i] },
    { group: "Exploration",     groupRe: /explor/i,  cats: [/book\s*swap/i, /magazine/i, /1010/i] },
    { group: "Activities",      groupRe: /activit/i, cats: [/fishing/i] },
    { group: "Stunts",          groupRe: /stunt/i,   cats: [/stunt\s*jump/i, /knife/i, /base\s*jump/i, /bridge/i] },
  ];

  const asArr = (v) => (Array.isArray(v) ? v : v && typeof v === "object" ? Object.values(v) : []);
  const locs = asArr(mapData.locations);

  const cats = new Map();
  const groupTitle = new Map();
  const addGroup = (g) => { if (g && g.id != null && g.title) groupTitle.set(g.id, g.title); };
  const addCat = (c) => {
    if (!c || c.id == null || !c.title) return;
    cats.set(c.id, c);
    if (c.group) addGroup(c.group);
  };
  for (const k of ["groups", "category_groups", "categoryGroups"]) {
    asArr(mapData[k]).forEach((g) => { addGroup(g); asArr(g && g.categories).forEach(addCat); });
  }
  asArr(mapData.categories).forEach(addCat);
  locs.forEach((l) => addCat(l.category));

  const counts = new Map();
  locs.forEach((l) => counts.set(l.category_id, (counts.get(l.category_id) || 0) + 1));

  const chosen = new Map();
  const notFound = [];
  for (const w of WANT) {
    for (const re of w.cats) {
      const hits = [...cats.values()].filter((c) => {
        if (!re.test(c.title)) return false;
        const gt = groupTitle.get(c.group_id);
        return !gt || w.groupRe.test(gt);
      });
      if (!hits.length) notFound.push(`${w.group}: ${re}`);
      hits.forEach((c) => { if (!chosen.has(c.id)) chosen.set(c.id, { group: w.group, cat: c }); });
    }
  }

  const clean = (s) => (s || "")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\*\*|__/g, "")
    .replace(/\s+/g, " ").trim();
  const out = [];
  for (const l of locs) {
    const ch = chosen.get(l.category_id);
    if (!ch) continue;
    out.push({
      id: l.id,
      group: ch.group,
      set: ch.cat.title,
      title: l.title || ch.cat.title,
      lat: l.latitude,
      lng: l.longitude,
      description: clean(l.description),
      images: (l.media || []).filter((m) => m && m.type === "image" && m.url)
                             .sort((a, b) => (a.order || 0) - (b.order || 0)).map((m) => m.url),
    });
  }

  const lines = [];
  for (const { group, cat } of chosen.values()) {
    lines.push(`  ${group.padEnd(16)} | ${cat.title}  (group on site: ${groupTitle.get(cat.group_id) || "?"}, ${counts.get(cat.id) || 0} markers)`);
  }
  console.log(`Exporting ${out.length} markers from ${chosen.size} categories:\n` + lines.join("\n"));
  if (notFound.length) console.warn("NOT FOUND (no category title matched):\n  " + notFound.join("\n  "));
  const all = [...cats.values()].map((c) => `  ${(groupTitle.get(c.group_id) || "group " + c.group_id)} | ${c.title} | ${counts.get(c.id) || 0}`).sort();
  console.log("All categories on this map (group | category | markers):\n" + all.join("\n"));

  const blob = new Blob([JSON.stringify(out)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "extras.json";
  a.click();
})();
