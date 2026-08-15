"""Generate the static site (site/index.html + downloadable CSVs) from the data CSVs."""

import csv
import json
import shutil
from datetime import date

from config import DATA_DIR, SITE_DIR, STORIES_CSV
from store import load_stories

COURT_CSV = DATA_DIR / "court_records.csv"

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flock Crime Prevention Tracker</title>
<meta name="description" content="A daily-updated database of news stories in which Flock Safety cameras helped solve or prevent a crime.">
<meta property="og:title" content="Flock Crime Prevention Tracker">
<meta property="og:description" content="A daily-updated, independently sourced database of Flock Safety cameras helping solve or prevent crimes.">
<meta property="og:url" content="https://flockstopscrime.com/">
<meta property="og:image" content="https://flockstopscrime.com/og-image.png">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://flockstopscrime.com/og-image.png">
<style>
  :root {
    --ground: #f6f8fb;
    --card: #ffffff;
    --ink: #2b3440;
    --ink-strong: #131a22;
    --muted: #64748b;
    --accent: #2a78d6;
    --burgundy: #1c5cab;
    --teal: #3f7d74;
    --hairline: #dde4ed;
    --grid: #e9eef5;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--ground); color: var(--ink);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height: 1.5;
  }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 0 20px; }
  header { padding: 48px 0 8px; }
  h1 { font-size: 2rem; margin: 0 0 6px; color: var(--ink-strong); letter-spacing: -0.01em; }
  .subtitle { font-family: Georgia, serif; font-style: italic; color: var(--muted); margin: 0 0 4px; font-size: 1.05rem; }
  .updated { font-size: 0.85rem; color: var(--muted); margin: 0; }
  nav.toc { margin-top: 14px; font-size: 0.85rem; display: flex; gap: 18px; flex-wrap: wrap; }
  nav.toc a { color: var(--burgundy); text-decoration: none; border-bottom: 1px solid var(--hairline); padding-bottom: 1px; }
  nav.toc a:hover { border-color: var(--burgundy); }
  .banner { border-radius: 14px; overflow: hidden; margin: 28px 0;
    background: linear-gradient(135deg, #1c5cab 0%, #2a78d6 100%);
    color: #fff; box-shadow: 0 6px 24px rgba(28,92,171,0.25); }
  .banner-main { padding: 30px 36px 22px; }
  .hero { font-size: 3.4rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1; font-variant-numeric: tabular-nums; }
  .hero-label { font-size: 1.15rem; font-weight: 500; opacity: 0.95; margin-top: 6px; max-width: 46em; }
  .substats { display: flex; gap: 34px; margin-top: 22px; flex-wrap: wrap; }
  .substat .n { font-size: 1.45rem; font-weight: 700; font-variant-numeric: tabular-nums; }
  .substat .l { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.85; }
  .banner-foot { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
    background: rgba(0,0,0,0.18); padding: 10px 36px; font-size: 0.85rem; }
  .banner-foot .brand { font-weight: 700; }
  .banner-foot .bdate { opacity: 0.85; }
  .charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; margin-bottom: 28px; }
  .chart-card { background: var(--card); border: 1px solid var(--hairline); border-radius: 10px; padding: 16px 18px; }
  .chart-card h3 { margin: 0 0 10px; font-size: 0.95rem; color: var(--ink-strong); }
  .chart-card svg { width: 100%; height: auto; display: block; }
  .filters { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 12px; align-items: center; }
  .filters input, .filters select {
    font: inherit; color: var(--ink); background: var(--card);
    border: 1px solid var(--hairline); border-radius: 8px; padding: 8px 10px;
  }
  .filters input { flex: 1 1 220px; min-width: 180px; }
  .count { font-size: 0.85rem; color: var(--muted); margin-left: auto; }
  .table-wrap { overflow-x: auto; background: var(--card); border: 1px solid var(--hairline); border-radius: 10px; }
  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; min-width: 860px; }
  th, td { text-align: left; padding: 10px 12px; vertical-align: top; border-top: 1px solid var(--grid); }
  thead th { border-top: none; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); position: sticky; top: 0; background: var(--card); }
  thead th.sortable { cursor: pointer; user-select: none; white-space: nowrap; }
  thead th.sortable:hover { color: var(--ink-strong); }
  tbody tr:nth-child(even) { background: #f7f9fc; }
  tbody tr:hover { background: #eef3fa; }
  .clear-btn { font: inherit; font-size: 0.85rem; background: none; border: 1px solid var(--hairline); border-radius: 8px; padding: 8px 12px; color: var(--muted); cursor: pointer; }
  .clear-btn:hover { color: var(--ink-strong); border-color: var(--muted); }
  td.date { white-space: nowrap; font-variant-numeric: tabular-nums; }
  td.loc { white-space: nowrap; }
  td.summary { min-width: 320px; }
  a { color: var(--burgundy); }
  .srclink { font-size: 0.85rem; }
  .pill { display: inline-block; background: #e6eefb; border-radius: 999px; padding: 1px 9px; font-size: 0.8rem; color: #1c5cab; white-space: nowrap; }
  .type-news { display: inline-block; border: 1px solid #b7cdf0; border-radius: 999px; padding: 1px 9px; font-size: 0.75rem; color: #1c5cab; }
  .type-court { display: inline-block; border-radius: 999px; padding: 1px 9px; font-size: 0.75rem; color: #fff; background: #1c5cab; }
  .more { text-align: center; padding: 14px; }
  .more button { font: inherit; background: var(--accent); color: #fff; border: none; border-radius: 8px; padding: 8px 18px; cursor: pointer; }
  section.method { margin: 40px 0; font-size: 0.92rem; }
  section.method h2 { font-size: 1.15rem; color: var(--ink-strong); }
  footer { margin: 40px 0 30px; padding-top: 16px; border-top: 1px solid var(--hairline); font-family: Georgia, serif; font-style: italic; font-size: 0.85rem; color: var(--muted); }
  .dl { display: inline-block; margin: 6px 0 0; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Flock Crime Prevention Tracker</h1>
    <p class="subtitle">A daily-updated database of news stories in which Flock Safety cameras helped solve or prevent a crime.</p>
    <p class="updated">Last updated __UPDATED__ &middot; Download: <a class="dl" href="stories.csv" download>news stories (CSV)</a> &middot; <a class="dl" href="court_records.csv" download>court records (CSV)</a></p>
    <nav class="toc">
      <a href="#database">Database</a>
      <a href="#method">Methodology</a>
      <a href="https://github.com/CharlesFainLehman/flock-crime-tracker">Data &amp; code</a>
      <a href="https://github.com/CharlesFainLehman/flock-crime-tracker/issues/new/choose">Flag an error / suggest a story</a>
    </nav>
  </header>

  <div class="banner" id="banner">
    <div class="banner-main">
      <div class="hero" id="b-hero"></div>
      <div class="hero-label" id="b-label"></div>
      <div class="substats" id="b-substats"></div>
    </div>
    <div class="banner-foot">
      <span class="brand">flockstopscrime.com</span>
      <span class="bdate" id="b-foot">updated __UPDATED__ &middot; every case independently sourced</span>
    </div>
  </div>

  <div class="charts">
    <div class="chart-card"><h3>Incidents by year</h3><div id="chart-year"></div></div>
    <div class="chart-card"><h3>Most common crime types</h3><div id="chart-crime"></div></div>
    <div class="chart-card"><h3>Top states</h3><div id="chart-state"></div></div>
  </div>

  <div class="filters" id="database">
    <input id="q" type="search" placeholder="Search city, outlet, summary&hellip;" aria-label="Search stories">
    <select id="f-type" aria-label="Filter by source type"><option value="">All sources</option><option value="news">News stories</option><option value="court">Court records</option></select>
    <select id="f-state" aria-label="Filter by state"><option value="">All states</option></select>
    <select id="f-crime" aria-label="Filter by crime type"><option value="">All crime types</option></select>
    <select id="f-year" aria-label="Filter by year"><option value="">All years</option></select>
    <button class="clear-btn" id="clear" hidden>Clear filters</button>
    <span class="count" id="count"></span>
  </div>

  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Type</th>
        <th class="sortable" data-sort="date">Date <span class="arrow"></span></th>
        <th class="sortable" data-sort="loc">Location <span class="arrow"></span></th>
        <th class="sortable" data-sort="crime">Crime <span class="arrow"></span></th>
        <th>Camera role</th>
        <th>Outcome</th><th>Summary</th><th>Source</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <div class="more" id="more" hidden><button id="more-btn">Show more</button></div>
  </div>

  <section class="method" id="method">
    <h2>Methodology</h2>
    <p>This database is assembled automatically each day. Candidate articles are gathered from the
    <a href="https://www.gdeltproject.org/">GDELT Project</a> and Google News using searches for Flock
    Safety cameras in crime coverage. Each article is then classified by a large language model
    (Anthropic&rsquo;s Claude) to determine whether it describes a concrete incident in which a Flock
    camera assisted in solving or preventing a crime &mdash; excluding privacy debates, procurement news,
    and company press releases &mdash; and to extract the date, location, crime type, the camera&rsquo;s
    role, and the outcome. Stories covering the same incident are merged into a single entry.</p>
    <p>Entries reflect claims made in news reports, which typically rely on police statements; inclusion
    here is not an independent verification of the camera&rsquo;s role. Coverage is limited to English-language
    outlets indexed by the sources above, so the database understates the true number of such incidents.
    Each entry links to its source article(s). The full dataset is available as a
    <a href="stories.csv">CSV download</a>. Spotted an error or a missing incident?
    <a href="https://github.com/CharlesFainLehman/flock-crime-tracker/issues/new/choose">File a report</a> —
    submissions are automatically checked against the database and cited sources, then
    reviewed by the maintainer; every accepted correction is public in the
    <a href="https://github.com/CharlesFainLehman/flock-crime-tracker/commits/main">edit history</a>.</p>
  </section>

  <footer>
    <p>Created by <a href="https://x.com/charlesflehman">Charles Fain Lehman</a>.</p>
    <p>Built and maintained in collaboration with <a href="https://claude.com">Claude</a> (Anthropic).
    Claude wrote the data pipeline and this site, and runs the daily update: gathering candidate
    articles via <a href="https://www.gdeltproject.org/">GDELT</a> and Google News, reading and
    classifying each one, extracting the structured fields, merging duplicate coverage, and
    republishing the database. Court records are gathered via
    <a href="https://www.courtlistener.com/">CourtListener</a>/RECAP.</p>
  </footer>
</div>

<script id="data" type="application/json">__DATA_JSON__</script>
<script id="court-data" type="application/json">__COURT_JSON__</script>
<script>
(function () {
  var NEWS = JSON.parse(document.getElementById("data").textContent);
  var COURT = JSON.parse(document.getElementById("court-data").textContent);
  NEWS.forEach(function (r) { r.kind = "news"; r.court_links = []; });
  var byId = {};
  NEWS.forEach(function (r) { byId[r.id] = r; });
  var ALL = NEWS.slice();
  COURT.forEach(function (c) {
    var match = c.matched_story_id && byId[c.matched_story_id];
    if (match) { match.court_links.push(c.source_url); return; }
    ALL.push({
      kind: "court", id: "c" + c.id,
      incident_date: c.date_filed, date_added: c.date_added,
      city: "", state: c.state || "",
      crime_type: c.crime_type || "",
      camera_role: c.flock_role || "",
      outcome: c.record_type || "",
      summary: (c.case_name ? c.case_name + " — " : "") + (c.summary || ""),
      source_name: c.court || "court filing", source_url: c.source_url,
      additional_sources: "", confidence: c.confidence, court_links: []
    });
  });
  var PAGE = 25;
  var shown = PAGE;
  var sortKey = "date", sortDir = -1;

  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var yearOf = function (r) { return (r.incident_date || r.date_added || "").slice(0, 4); };

  // --- filters ---
  var q = document.getElementById("q");
  var fType = document.getElementById("f-type");
  var fState = document.getElementById("f-state");
  var fCrime = document.getElementById("f-crime");
  var fYear = document.getElementById("f-year");

  function fillSelect(sel, values) {
    values.forEach(function (v) {
      var o = document.createElement("option");
      o.value = v; o.textContent = v;
      sel.appendChild(o);
    });
  }
  fillSelect(fState, Array.from(new Set(ALL.map(function (r) { return r.state; }).filter(Boolean))).sort());
  fillSelect(fCrime, Array.from(new Set(ALL.map(function (r) { return r.crime_type; }).filter(Boolean))).sort());
  fillSelect(fYear, Array.from(new Set(ALL.map(yearOf).filter(Boolean))).sort().reverse());

  function filtered() {
    var needle = q.value.trim().toLowerCase();
    return ALL.filter(function (r) {
      if (fType.value && r.kind !== fType.value) return false;
      if (fState.value && r.state !== fState.value) return false;
      if (fCrime.value && r.crime_type !== fCrime.value) return false;
      if (fYear.value && yearOf(r) !== fYear.value) return false;
      if (needle) {
        var hay = (r.city + " " + r.state + " " + r.summary + " " + r.source_name + " " +
                   r.crime_type + " " + r.outcome + " " + r.camera_role).toLowerCase();
        if (hay.indexOf(needle) === -1) return false;
      }
      return true;
    });
  }

  // --- share banner ---
  function renderBanner(rows) {
    var states = new Set(rows.map(function (r) { return r.state; }).filter(Boolean));
    var years = rows.map(yearOf).filter(Boolean).sort();
    var byCrime = {};
    rows.forEach(function (r) { if (r.crime_type) byCrime[r.crime_type] = (byCrime[r.crime_type] || 0) + 1; });
    var top = Object.keys(byCrime).sort(function (a, b) { return byCrime[b] - byCrime[a]; }).slice(0, 2);
    document.getElementById("b-hero").textContent = rows.length;
    document.getElementById("b-label").textContent =
      "documented case" + (rows.length === 1 ? "" : "s") +
      " of Flock Safety cameras helping solve or prevent a crime";
    var subs = [];
    subs.push({ n: states.size, l: "state" + (states.size === 1 ? "" : "s") });
    if (years.length) subs.push({ n: years[0] === years[years.length - 1] ? years[0] : years[0] + "\u2013" + years[years.length - 1], l: "coverage" });
    top.forEach(function (k) { subs.push({ n: byCrime[k], l: k }); });
    document.getElementById("b-substats").innerHTML = subs.map(function (x) {
      return '<div class="substat"><div class="n">' + esc(x.n) + '</div><div class="l">' + esc(x.l) + "</div></div>";
    }).join("");
    var filt = [];
    if (fType.value) filt.push(fType.value === "news" ? "news stories" : "court records");
    if (fState.value) filt.push(fState.value);
    if (fCrime.value) filt.push(fCrime.value);
    if (fYear.value) filt.push(fYear.value);
    if (q.value.trim()) filt.push('"' + q.value.trim() + '"');
    var base = "updated __UPDATED__ \u00b7 every case independently sourced";
    document.getElementById("b-foot").textContent =
      filt.length ? base + " \u00b7 filtered: " + filt.join(" \u00b7 ") : base;
  }

  // --- charts (inline SVG, single amber series, direct value labels) ---
  function barChartV(counts, keys) {
    var W = 480, H = 220, padB = 26, padT = 18, padL = 8, padR = 8;
    var max = Math.max.apply(null, keys.map(function (k) { return counts[k]; }).concat([1]));
    var bw = (W - padL - padR) / keys.length;
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Incidents by year">';
    s += '<line x1="' + padL + '" y1="' + (H - padB) + '" x2="' + (W - padR) + '" y2="' + (H - padB) + '" stroke="#b8c4d4" stroke-width="1"/>';
    keys.forEach(function (k, i) {
      var v = counts[k];
      var h = Math.round((H - padB - padT) * v / max);
      var x = padL + i * bw + bw * 0.15, w = bw * 0.7;
      var y = H - padB - h;
      s += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + Math.max(h, 1) + '" rx="4" fill="#2a78d6"/>';
      s += '<text x="' + (x + w / 2) + '" y="' + (y - 5) + '" text-anchor="middle" font-size="11" fill="#2b3440">' + v + "</text>";
      s += '<text x="' + (x + w / 2) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="11" fill="#64748b">' + esc(k) + "</text>";
    });
    return s + "</svg>";
  }
  function barChartH(counts, keys) {
    var W = 480, rowH = 26, padT = 4, labelW = 170;
    var H = padT + keys.length * rowH + 6;
    var max = Math.max.apply(null, keys.map(function (k) { return counts[k]; }).concat([1]));
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Most common crime types">';
    keys.forEach(function (k, i) {
      var v = counts[k];
      var y = padT + i * rowH;
      var w = Math.max(Math.round((W - labelW - 44) * v / max), 2);
      s += '<text x="' + (labelW - 8) + '" y="' + (y + rowH / 2 + 4) + '" text-anchor="end" font-size="11.5" fill="#2b3440">' + esc(k) + "</text>";
      s += '<rect x="' + labelW + '" y="' + (y + 4) + '" width="' + w + '" height="' + (rowH - 10) + '" rx="4" fill="#2a78d6"/>';
      s += '<text x="' + (labelW + w + 6) + '" y="' + (y + rowH / 2 + 4) + '" font-size="11" fill="#2b3440">' + v + "</text>";
    });
    return s + "</svg>";
  }
  function renderCharts(rows) {
    var byYear = {};
    rows.forEach(function (r) { var y = yearOf(r); if (y) byYear[y] = (byYear[y] || 0) + 1; });
    var years = Object.keys(byYear).sort();
    document.getElementById("chart-year").innerHTML =
      years.length ? barChartV(byYear, years) : '<p style="color:#64748b">No data yet.</p>';

    var byCrime = {};
    rows.forEach(function (r) { if (r.crime_type) byCrime[r.crime_type] = (byCrime[r.crime_type] || 0) + 1; });
    var crimes = Object.keys(byCrime).sort(function (a, b) { return byCrime[b] - byCrime[a]; }).slice(0, 8);
    document.getElementById("chart-crime").innerHTML =
      crimes.length ? barChartH(byCrime, crimes) : '<p style="color:#64748b">No data yet.</p>';

    var byState = {};
    rows.forEach(function (r) { if (r.state) byState[r.state] = (byState[r.state] || 0) + 1; });
    var states = Object.keys(byState).sort(function (a, b) { return byState[b] - byState[a]; }).slice(0, 8);
    document.getElementById("chart-state").innerHTML =
      states.length ? barChartH(byState, states) : '<p style="color:#64748b">No data yet.</p>';
  }

  // --- table ---
  function sourceCell(r) {
    var links = ['<a class="srclink" href="' + esc(r.source_url) + '" rel="nofollow noopener">' + esc(r.source_name || "link") + "</a>"];
    (r.additional_sources || "").split(" ").filter(Boolean).forEach(function (u, i) {
      links.push('<a class="srclink" href="' + esc(u) + '" rel="nofollow noopener">+' + (i + 2) + "</a>");
    });
    (r.court_links || []).forEach(function (u) {
      links.push('<a class="srclink" href="' + esc(u) + '" rel="nofollow noopener" title="Related court filing">&#9878; docket</a>');
    });
    links.push('<a class="srclink" style="opacity:0.55" title="Flag an error in this record" href="https://github.com/CharlesFainLehman/flock-crime-tracker/issues/new?template=flag-error.yml&record-id=' + esc(r.id) + '" rel="nofollow noopener">&#9873;</a>');
    return links.join(" ");
  }
  function renderTable(rows) {
    var body = rows.slice(0, shown).map(function (r) {
      return "<tr>" +
        '<td><span class="type-' + r.kind + '">' + (r.kind === "news" ? "news" : "court") + "</span></td>" +
        '<td class="date">' + esc(r.incident_date || r.date_added) + "</td>" +
        '<td class="loc">' + esc(r.city ? r.city + ", " + r.state : r.state) + "</td>" +
        '<td><span class="pill">' + esc(r.crime_type) + "</span></td>" +
        "<td>" + esc(r.camera_role) + "</td>" +
        "<td>" + esc(r.outcome) + "</td>" +
        '<td class="summary">' + esc(r.summary) + "</td>" +
        "<td>" + sourceCell(r) + "</td>" +
        "</tr>";
    }).join("");
    document.getElementById("rows").innerHTML =
      body || '<tr><td colspan="8" style="color:#64748b">No matching stories.</td></tr>';
    document.getElementById("count").textContent =
      rows.length + " of " + ALL.length + " records";
    document.getElementById("more").hidden = rows.length <= shown;
  }

  function sortVal(r) {
    if (sortKey === "date") return r.incident_date || r.date_added || "";
    if (sortKey === "loc") return (r.state || "") + " " + (r.city || "");
    return r.crime_type || "";
  }
  function render() {
    var rows = filtered();
    rows.sort(function (a, b) {
      var va = sortVal(a), vb = sortVal(b);
      return va < vb ? -sortDir : va > vb ? sortDir : 0;
    });
    renderBanner(rows);
    renderCharts(rows);
    renderTable(rows);
    document.querySelectorAll("th.sortable .arrow").forEach(function (el) { el.textContent = ""; });
    var active = document.querySelector('th.sortable[data-sort="' + sortKey + '"] .arrow');
    if (active) active.textContent = sortDir === 1 ? "▲" : "▼";
    var any = q.value || fType.value || fState.value || fCrime.value || fYear.value;
    document.getElementById("clear").hidden = !any;
    var hash = ["q=" + encodeURIComponent(q.value), "type=" + fType.value, "state=" + fState.value,
                "crime=" + encodeURIComponent(fCrime.value), "year=" + fYear.value]
      .filter(function (kv) { return kv.split("=")[1]; }).join("&");
    try {
      history.replaceState(null, "", hash ? "#" + hash : location.pathname);
    } catch (e) { /* sandboxed contexts (previews) disallow replaceState */ }
  }

  document.querySelectorAll("th.sortable").forEach(function (th) {
    th.addEventListener("click", function () {
      var k = th.getAttribute("data-sort");
      if (sortKey === k) { sortDir = -sortDir; } else { sortKey = k; sortDir = k === "date" ? -1 : 1; }
      render();
    });
  });
  [q, fType, fState, fCrime, fYear].forEach(function (el) {
    el.addEventListener("input", function () { shown = PAGE; render(); });
  });
  document.getElementById("clear").addEventListener("click", function () {
    q.value = ""; fType.value = ""; fState.value = ""; fCrime.value = ""; fYear.value = "";
    shown = PAGE; render();
  });
  document.getElementById("more-btn").addEventListener("click", function () {
    shown += PAGE; render();
  });

  // Restore shareable filter state from the URL hash.
  if (location.hash.length > 1) {
    location.hash.slice(1).split("&").forEach(function (kv) {
      var k = kv.split("=")[0], v = decodeURIComponent(kv.split("=").slice(1).join("="));
      if (k === "q") q.value = v;
      if (k === "type") fType.value = v;
      if (k === "state") fState.value = v;
      if (k === "crime") fCrime.value = v;
      if (k === "year") fYear.value = v;
    });
  }
  document.querySelectorAll("[data-type-link]").forEach(function (a) {
    a.addEventListener("click", function () {
      fType.value = a.getAttribute("data-type-link"); shown = PAGE; render();
    });
  });
  render();

})();
</script>
</body>
</html>
"""


def build_site() -> None:
    stories = load_stories()
    courts = []
    if COURT_CSV.exists():
        with open(COURT_CSV, newline="", encoding="utf-8") as f:
            courts = list(csv.DictReader(f))
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(stories, ensure_ascii=False).replace("</", "<\\/")
    court_payload = json.dumps(courts, ensure_ascii=False).replace("</", "<\\/")
    html = (TEMPLATE
            .replace("__DATA_JSON__", payload)
            .replace("__COURT_JSON__", court_payload)
            .replace("__UPDATED__", date.today().strftime("%B %-d, %Y")))
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")

    (SITE_DIR / "CNAME").write_text("flockstopscrime.com\n")
    from make_og_image import make_og_image
    make_og_image()
    if STORIES_CSV.exists():
        shutil.copy(STORIES_CSV, SITE_DIR / "stories.csv")
    if COURT_CSV.exists():
        shutil.copy(COURT_CSV, SITE_DIR / "court_records.csv")
    print(f"Site built with {len(stories)} stories, {len(courts)} court records "
          f"-> {SITE_DIR / 'index.html'}")


if __name__ == "__main__":
    build_site()
