(() => {
  const locs = Object.values(window.mapData.locations);
  const result = {};
  let withImages = 0, withDesc = 0;
  for (const l of locs) {
    const images = (l.media || [])
      .filter((m) => m && m.type === "image" && m.url)
      .sort((a, b) => (a.order || 0) - (b.order || 0))
      .map((m) => m.url);
    const description = (l.description || "").replace(/\*\*|__/g, "").replace(/\s+/g, " ").trim();
    result[l.id] = { title: l.title || "", description, images };
    if (images.length) withImages++;
    if (description) withDesc++;
  }
  console.log(`${locs.length} locations, ${withDesc} with a description, ${withImages} with images`);

  const blob = new Blob([JSON.stringify(result)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "cards_info.json";
  a.click();
})();
