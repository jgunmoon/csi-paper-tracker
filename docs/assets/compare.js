// Tag filter, text search and column sort for the comparison table (compare.md).
// Within one tag group the selected tags are OR'ed; across groups they are AND'ed.
(function () {
  function init() {
    const table = document.querySelector("table.csi-compare");
    if (!table || table.dataset.ready) return;
    table.dataset.ready = "1";
    const rows = Array.from(table.tBodies[0].rows);
    const buttons = Array.from(document.querySelectorAll(".csi-filter"));
    const search = document.querySelector(".csi-search");
    const count = document.querySelector(".csi-count");

    function apply() {
      const active = {};
      buttons.forEach((b) => {
        if (b.getAttribute("aria-pressed") === "true") {
          const g = b.closest(".csi-filter-group").dataset.group;
          (active[g] = active[g] || []).push(b.dataset.tag);
        }
      });
      const q = (search && search.value.trim().toLowerCase()) || "";
      let shown = 0;
      rows.forEach((r) => {
        const tags = r.dataset.tags.split(" ");
        const okTags = Object.values(active).every((sel) => sel.some((t) => tags.includes(t)));
        const okText = !q || r.dataset.search.includes(q);
        r.hidden = !(okTags && okText);
        if (!r.hidden) shown++;
      });
      if (count) count.textContent = `${shown} / ${rows.length}편`;
    }

    buttons.forEach((b) => b.addEventListener("click", () => {
      b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") === "true" ? "false" : "true");
      apply();
    }));
    if (search) search.addEventListener("input", apply);
    const reset = document.querySelector(".csi-reset");
    if (reset) reset.addEventListener("click", () => {
      buttons.forEach((b) => b.setAttribute("aria-pressed", "false"));
      if (search) search.value = "";
      apply();
    });

    table.querySelectorAll("th[data-sort]").forEach((th) => {
      th.tabIndex = 0;
      th.title = "정렬";
      const sort = () => {
        const idx = th.cellIndex;
        const num = th.dataset.sort === "num";
        const dir = th.dataset.dir === "desc" ? "asc" : "desc";
        table.querySelectorAll("th").forEach((h) => delete h.dataset.dir);
        th.dataset.dir = dir;
        const key = (r) => {
          const c = r.cells[idx];
          return num ? parseFloat(c.dataset.value || c.textContent) || 0 : c.textContent.trim().toLowerCase();
        };
        rows.sort((a, b) => (key(a) > key(b) ? 1 : key(a) < key(b) ? -1 : 0) * (dir === "asc" ? 1 : -1));
        rows.forEach((r) => table.tBodies[0].appendChild(r));
      };
      th.addEventListener("click", sort);
      th.addEventListener("keydown", (e) => { if (e.key === "Enter") sort(); });
    });
    apply();
  }
  if (typeof document$ !== "undefined") document$.subscribe(init);
  else document.addEventListener("DOMContentLoaded", init);
})();
