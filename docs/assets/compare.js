// Comparison table (compare.md): tag/agenda filters, v1 period and minimum-score choices, text search
// and sorting. The whole state is mirrored in the page URL (?topic=AI&agenda=127-9.1.1&period=4w&min=60
// &search=srs&sort=score) so a filtered view can be shared as a link; defaults are left out of the URL.
// (Not `q`: Material for MkDocs opens its own search dialog when the URL has ?q=.)
// Within one button group the selected values are OR'ed; across groups they are AND'ed.
(function () {
  const DEFAULT_SORT = "date";
  const TEXT_KEYS = ["title", "channel"]; // sorted A→Z on first click; everything else high→low

  function isoDay(d) {
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  // First v1 date (YYYY-MM-DD) still inside the chosen period, or null for "all".
  function periodStart(period) {
    const d = new Date();
    if (period === "4w") d.setDate(d.getDate() - 28);
    else if (period === "3m") d.setMonth(d.getMonth() - 3);
    else return null;
    return isoDay(d);
  }

  function init() {
    const table = document.querySelector("table.csi-compare");
    if (!table || table.dataset.ready) return;
    table.dataset.ready = "1";
    const body = table.tBodies[0];
    const empty = body.querySelector(".csi-empty");
    const rows = Array.from(body.rows).filter((r) => r !== empty);
    const filters = Array.from(document.querySelectorAll(".csi-filter"));
    const choices = Array.from(document.querySelectorAll(".csi-choice"));
    const headers = Array.from(table.querySelectorAll("th[data-key]"));
    const search = document.querySelector(".csi-search");
    const sortSel = document.querySelector(".csi-sort");
    const count = document.querySelector(".csi-count");
    const state = { sort: DEFAULT_SORT, dir: "desc" };

    rows.forEach((r) => {
      try { r.csiScores = JSON.parse(r.dataset.scores || "{}"); } catch (e) { r.csiScores = {}; }
    });

    const pressed = (b) => b.getAttribute("aria-pressed") === "true";
    const press = (b, on) => b.setAttribute("aria-pressed", on ? "true" : "false");
    const groupOf = (b) => b.closest("[data-group]").dataset.group;
    const paramOf = (b) => b.closest("[data-param]").dataset.param;

    function choice(param) {
      const b = choices.find((c) => paramOf(c) === param && pressed(c));
      return b ? b.dataset.value : "all";
    }
    function setChoice(param, value) {
      const group = choices.filter((c) => paramOf(c) === param);
      const target = group.some((c) => c.dataset.value === value) ? value : "all";
      group.forEach((c) => press(c, c.dataset.value === target));
    }

    function validKey(k) {
      return k === "date" || k === "score" || headers.some((h) => h.dataset.key === k) ||
        (sortSel && Array.from(sortSel.options).some((o) => o.value && o.value === k));
    }

    function sortValue(r, k) {
      if (k === "date") return r.dataset.date || "";
      if (k === "score") return parseFloat(r.dataset.score) || 0;
      if (k in r.csiScores) return Number(r.csiScores[k]) || 0;
      const th = headers.find((h) => h.dataset.key === k);
      return th ? r.cells[th.cellIndex].textContent.trim().toLowerCase() : "";
    }

    function sortRows() {
      const k = state.sort;
      const sign = state.dir === "asc" ? 1 : -1;
      rows.sort((a, b) => {
        const x = sortValue(a, k);
        const y = sortValue(b, k);
        if (x < y) return -sign;
        if (x > y) return sign;
        return (b.dataset.date || "").localeCompare(a.dataset.date || ""); // ties: newest first
      });
      rows.forEach((r) => body.insertBefore(r, empty));
      headers.forEach((h) => {
        if (h.dataset.key === k) h.dataset.dir = state.dir;
        else delete h.dataset.dir;
        h.setAttribute("aria-sort", h.dataset.key === k ? (state.dir === "asc" ? "ascending" : "descending") : "none");
      });
      if (sortSel) {
        const listed = Array.from(sortSel.options).some((o) => o.value === k);
        sortSel.value = listed && state.dir === "desc" ? k : "";
      }
    }

    function writeUrl() {
      const parts = [];
      const byGroup = {};
      filters.forEach((b) => {
        if (pressed(b)) (byGroup[groupOf(b)] = byGroup[groupOf(b)] || []).push(b.dataset.key);
      });
      Object.keys(byGroup).forEach((g) => parts.push(`${g}=${byGroup[g].map(encodeURIComponent).join(",")}`));
      ["period", "min"].forEach((p) => {
        const v = choice(p);
        if (v !== "all") parts.push(`${p}=${encodeURIComponent(v)}`);
      });
      const q = search ? search.value.trim() : "";
      if (q) parts.push(`search=${encodeURIComponent(q)}`);
      if (state.sort !== DEFAULT_SORT || state.dir !== "desc") {
        parts.push(`sort=${encodeURIComponent(state.sort)}${state.dir === "asc" ? "-asc" : ""}`);
      }
      const url = location.pathname + (parts.length ? "?" + parts.join("&") : "") + location.hash;
      try { history.replaceState(history.state, "", url); } catch (e) { /* file:// or sandboxed preview */ }
    }

    function readUrl() {
      const p = new URLSearchParams(location.search);
      filters.forEach((b) => {
        const keys = (p.get(groupOf(b)) || "").split(",").filter(Boolean);
        press(b, keys.includes(b.dataset.key));
      });
      setChoice("period", p.get("period") || "all");
      setChoice("min", p.get("min") || "all");
      if (search) search.value = p.get("search") || "";
      const s = p.get("sort") || DEFAULT_SORT;
      const asc = s.endsWith("-asc");
      const k = asc ? s.slice(0, -4) : s;
      state.sort = validKey(k) ? k : DEFAULT_SORT;
      state.dir = validKey(k) && asc ? "asc" : "desc";
    }

    function apply() {
      const active = {};
      filters.forEach((b) => {
        if (pressed(b)) (active[groupOf(b)] = active[groupOf(b)] || []).push(b.dataset.tag);
      });
      const q = search ? search.value.trim().toLowerCase() : "";
      const since = periodStart(choice("period"));
      const min = parseFloat(choice("min")) || 0;
      let shown = 0;
      rows.forEach((r) => {
        const tags = r.dataset.tags.split(" ");
        const ok = Object.values(active).every((sel) => sel.some((t) => tags.includes(t))) &&
          (!q || r.dataset.search.includes(q)) &&
          (!since || (r.dataset.date || "") >= since) &&
          (parseFloat(r.dataset.score) || 0) >= min;
        r.hidden = !ok;
        if (ok) shown++;
      });
      if (empty) empty.hidden = shown > 0;
      if (count) count.textContent = `${shown} / ${rows.length}편`;
      writeUrl();
    }

    filters.forEach((b) => b.addEventListener("click", () => { press(b, !pressed(b)); apply(); }));
    choices.forEach((b) => b.addEventListener("click", () => { setChoice(paramOf(b), b.dataset.value); apply(); }));
    if (search) search.addEventListener("input", apply);
    if (sortSel) sortSel.addEventListener("change", () => {
      if (!sortSel.value) return;
      state.sort = sortSel.value;
      state.dir = "desc";
      sortRows();
      apply();
    });
    headers.forEach((th) => {
      th.tabIndex = 0;
      th.title = "정렬";
      const sortBy = () => {
        const k = th.dataset.key;
        if (state.sort === k) state.dir = state.dir === "asc" ? "desc" : "asc";
        else state.dir = TEXT_KEYS.includes(k) ? "asc" : "desc";
        state.sort = k;
        sortRows();
        apply();
      };
      th.addEventListener("click", sortBy);
      th.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sortBy(); } });
    });

    const reset = document.querySelector(".csi-reset");
    if (reset) reset.addEventListener("click", () => {
      filters.forEach((b) => press(b, false));
      setChoice("period", "all");
      setChoice("min", "all");
      if (search) search.value = "";
      state.sort = DEFAULT_SORT;
      state.dir = "desc";
      sortRows();
      apply();
    });

    const copy = document.querySelector(".csi-copy");
    if (copy) copy.addEventListener("click", () => {
      const label = copy.textContent;
      const done = (text) => { copy.textContent = text; setTimeout(() => { copy.textContent = label; }, 1500); };
      const fallback = () => { window.prompt("이 주소를 복사하세요", location.href); };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(location.href).then(() => done("복사됨 ✓"), fallback);
      } else {
        fallback();
      }
    });

    readUrl();
    sortRows();
    apply();
  }

  if (typeof document$ !== "undefined") document$.subscribe(init);
  else document.addEventListener("DOMContentLoaded", init);
})();
