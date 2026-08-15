"""Generate the static site (site/index.html + downloadable CSVs) from the data CSVs."""

import csv
import json
import re
import shutil
from pathlib import Path
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
  .charts { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: auto auto; gap: 14px; margin-bottom: 28px; }
  .chart-card { background: var(--card); border: 1px solid var(--hairline); border-radius: 10px; padding: 16px 18px;
    display: flex; flex-direction: column; min-width: 0; }
  .chart-card h3 { margin: 0 0 10px; font-size: 0.95rem; color: var(--ink-strong); }
  .chart-card .chart-body { flex: 1; display: flex; flex-direction: column; justify-content: center; }
  .chart-card svg { width: 100%; height: auto; display: block; }
  .year-card, .crime-card { min-height: 0; }
  .map-card { grid-column: 1 / -1; }
  @media (max-width: 760px) {
    .charts { grid-template-columns: 1fr; }
    .map-card { grid-column: auto; }
    .chart-card { height: 380px; }
    .chart-card .chart-body { min-height: 0; overflow: hidden; }
    .chart-card svg { max-height: 100%; }
    .tiles { grid-template-columns: 1fr 1fr; grid-auto-rows: 1fr; }
    .tile { padding: 6px 8px; }
    .tile .t-n { font-size: 1.05rem; }
    .tile .t-l { font-size: 0.66rem; }
  }
  #chart-year rect[data-year] { transition: fill 0.12s; }
  #chart-year rect.bar-on:hover { fill: #1c5cab; }
  #chart-year rect.bar-off:hover { fill: #9ec5f4; }
  .usmap { width: 100%; max-width: 760px; margin: 0 auto; display: block; }
  .usmap path, .usmap circle { fill: none; stroke: none; pointer-events: none; }
  .usmap path.hit, .usmap circle.hit { fill: #e9eef5; stroke: #fff; stroke-width: 1; pointer-events: all; cursor: pointer; transition: filter 0.12s; }
  .usmap path.hit:hover, .usmap circle.hit:hover { filter: brightness(0.82); }
  .usmap path.selected, .usmap circle.selected { stroke: #131a22; stroke-width: 2; }
  .map-tooltip { position: fixed; pointer-events: none; background: #131a22; color: #fff;
    padding: 5px 10px; border-radius: 6px; font-size: 0.82rem; z-index: 10; display: none; white-space: nowrap; }
  .map-legend { display: flex; gap: 4px; align-items: center; justify-content: center; margin-top: 10px;
    font-size: 0.75rem; color: var(--muted); flex-wrap: wrap; }
  .map-legend .sw { width: 26px; height: 12px; border-radius: 3px; display: inline-block; }
  .tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; height: 100%; align-content: stretch; }
  .tile { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid var(--grid);
    border-radius: 9px; cursor: pointer; background: none; font: inherit; text-align: left; color: var(--ink); }
  .tile:hover { border-color: var(--accent); background: #f4f8fd; }
  .tile.selected { border-color: var(--accent); background: #e6eefb; }
  .tile.faded { opacity: 0.42; }
  .tile.faded:hover { opacity: 0.8; }
  .tile svg { width: 26px; height: 26px; flex: none; stroke: var(--accent); fill: none;
    stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  .tile .t-n { font-size: 1.25rem; font-weight: 700; color: var(--ink-strong); font-variant-numeric: tabular-nums; line-height: 1.1; }
  .tile .t-l { font-size: 0.74rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; overflow-wrap: anywhere; line-height: 1.2; display: block; }
  .tile > span:last-child { min-width: 0; }
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
      <span class="bdate" id="b-foot">updated __UPDATED__</span>
    </div>
  </div>

  <div class="charts">
    <div class="chart-card year-card"><h3>Cases by year <span style="font-weight:400;color:var(--muted);font-size:0.8rem">(click to filter)</span></h3><div class="chart-body" id="chart-year"></div></div>
    <div class="chart-card crime-card"><h3>Cases by crime type <span style="font-weight:400;color:var(--muted);font-size:0.8rem">(click to filter)</span></h3><div class="chart-body"><div class="tiles" id="chart-crime"></div></div></div>
    <div class="chart-card map-card"><h3>Cases by state <span style="font-weight:400;color:var(--muted);font-size:0.8rem">(hover for counts, click to filter)</span></h3>
      <div class="chart-body">__USMAP__</div>
      <div class="map-legend" id="map-legend"></div>
    </div>
  </div>
  <div class="map-tooltip" id="map-tip"></div>

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
    <p><strong>What counts.</strong> A record must describe a specific criminal incident in which a
    Flock license-plate-reader camera contributed to a concrete outcome: an arrest, the recovery of
    stolen property, the prevention of a crime in progress, or the identification of a suspect who was
    subsequently charged. Locating and apprehending a wanted suspect counts &mdash; the database is about
    cameras helping police solve and prevent crime, not about cameras working alone. Excluded by rule:
    missing-person recoveries with no underlying crime, cases with no resolved outcome at publication,
    aggregate deployment statistics, Flock&rsquo;s audio gunshot-detection products, and vendor press
    releases without independent coverage.</p>
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
  var yearOf = function (r) { return (r.incident_date || r.date_added || "").slice(0, 4); };
  var ALL_YEARS = Array.from(new Set(ALL.map(yearOf).filter(Boolean))).sort();
  var ALL_CRIME_COUNTS = {};
  ALL.forEach(function (r) { if (r.crime_type) ALL_CRIME_COUNTS[r.crime_type] = (ALL_CRIME_COUNTS[r.crime_type] || 0) + 1; });
  var ALL_CRIMES = Object.keys(ALL_CRIME_COUNTS).sort(function (a, b) { return ALL_CRIME_COUNTS[b] - ALL_CRIME_COUNTS[a]; }).slice(0, 8);

  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };

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

  function filtered(ignore) {
    var needle = q.value.trim().toLowerCase();
    return ALL.filter(function (r) {
      if (fType.value && r.kind !== fType.value) return false;
      if (ignore !== "state" && fState.value && r.state !== fState.value) return false;
      if (ignore !== "crime" && fCrime.value && r.crime_type !== fCrime.value) return false;
      if (ignore !== "year" && fYear.value && yearOf(r) !== fYear.value) return false;
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
    var base = "updated __UPDATED__";
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
      var active = !fYear.value || fYear.value === k;
      var fill = active ? "#2a78d6" : "#c9d8ee";
      var sel = fYear.value === k ? ' stroke="#131a22" stroke-width="2"' : "";
      s += '<rect data-year="' + esc(k) + '" class="' + (active ? "bar-on" : "bar-off") + '" style="cursor:pointer" x="' + x + '" y="' + y + '" width="' + w + '" height="' + Math.max(h, 1) + '" rx="4" fill="' + fill + '"' + sel + "/>";
      s += '<text x="' + (x + w / 2) + '" y="' + (y - 5) + '" text-anchor="middle" font-size="11" fill="' + (active ? "#2b3440" : "#a4b0c0") + '">' + v + "</text>";
      s += '<text data-year="' + esc(k) + '" style="cursor:pointer" x="' + (x + w / 2) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="11" fill="' + (active ? "#64748b" : "#a4b0c0") + '">' + esc(k) + "</text>";
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
    ALL_YEARS.forEach(function (y) { byYear[y] = 0; });
    filtered("year").forEach(function (r) { var y = yearOf(r); if (y in byYear) byYear[y] += 1; });
    document.getElementById("chart-year").innerHTML =
      ALL_YEARS.length ? barChartV(byYear, ALL_YEARS) : '<p style="color:#64748b">No data yet.</p>';

    renderCrimeTiles(rows);
    renderMap(rows);
  }

  // --- crime-type icon tiles ---
  var ICONS = {
    "vehicle theft": '<svg viewBox="0 0 24 24"><path d="M4 15l1.5-5.5c.2-.8.9-1.5 1.8-1.5h9.4c.9 0 1.6.7 1.8 1.5L20 15"/><path d="M3.5 15h17v3.5h-2"/><path d="M3.5 15v3.5h2"/><circle cx="7.5" cy="18.5" r="1.6"/><circle cx="16.5" cy="18.5" r="1.6"/></svg>',
    "carjacking": '<svg viewBox="0 0 24 24"><path d="M4 15l1.5-5.5c.2-.8.9-1.5 1.8-1.5h9.4c.9 0 1.6.7 1.8 1.5L20 15"/><path d="M3.5 15h17v3.5h-17z"/><path d="M12 2v4"/><path d="M10.5 3.5L12 2l1.5 1.5"/></svg>',
    "shooting": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/><circle cx="12" cy="12" r="1.2"/></svg>',
    "homicide": '<svg viewBox="0 0 24 24"><circle cx="12" cy="7" r="3.4"/><path d="M5.5 21c.5-4.5 3-7 6.5-7s6 2.5 6.5 7"/></svg>',
    "attempted homicide": '<svg viewBox="0 0 24 24"><circle cx="12" cy="7" r="3.4"/><path d="M5.5 21c.5-4.5 3-7 6.5-7s6 2.5 6.5 7"/><path d="M18 3l3 3M21 3l-3 3"/></svg>',
    "abduction/missing person": '<svg viewBox="0 0 24 24"><circle cx="10" cy="7" r="3.2"/><path d="M4 21c.4-4.2 2.7-6.6 6-6.6 1.2 0 2.3.3 3.2 1"/><path d="M17 13.5c0-1.4 1.1-2.3 2.4-2.3 1.4 0 2.4 1 2.4 2.2 0 1.7-2.3 1.8-2.3 3.4"/><circle cx="19.5" cy="20" r="0.4"/></svg>',
    "theft/larceny": '<svg viewBox="0 0 24 24"><rect x="3" y="8" width="18" height="10" rx="1.5"/><circle cx="12" cy="13" r="2.4"/><path d="M6 8V6.5M18 18v1.5"/></svg>',
    "robbery": '<svg viewBox="0 0 24 24"><path d="M9.5 6h5l2 3c1.8 2.7 2.5 5.5 2.5 8 0 2.4-3 4-7 4s-7-1.6-7-4c0-2.5.7-5.3 2.5-8z"/><path d="M9.5 6L8 3h8l-1.5 3"/><path d="M12 11v6M10.2 12.4h2.7c2 0 2 2.8-.9 2.8"/></svg>',
    "hit and run": '<svg viewBox="0 0 24 24"><path d="M7 13l1.2-4.4c.2-.7.8-1.1 1.5-1.1h7.6c.7 0 1.3.4 1.5 1.1L20 13"/><path d="M6.5 13h14v3h-14z"/><circle cx="9.5" cy="16" r="1.4"/><circle cx="17.5" cy="16" r="1.4"/><path d="M2 9h3M1 12h3M2 15h3"/></svg>',
    "burglary": '<svg viewBox="0 0 24 24"><path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/><path d="M14 14l2.5 2"/></svg>',
    "assault": '<svg viewBox="0 0 24 24"><path d="M12 3l2 4.5L18.5 6l-1.6 4.3L21 12l-4.1 1.7L18.5 18l-4.5-1.5L12 21l-2-4.5L5.5 18l1.6-4.3L3 12l4.1-1.7L5.5 6l4.5 1.5z"/></svg>',
    "fugitive apprehension": '<svg viewBox="0 0 24 24"><circle cx="7" cy="15" r="3.6"/><circle cx="17" cy="15" r="3.6"/><path d="M10.6 15h2.8"/><path d="M6 11.5V8c0-3 4-3 4 0"/><path d="M18 11.5V8c0-3-4-3-4 0"/></svg>',
    "weapons offense": '<svg viewBox="0 0 24 24"><path d="M3 8h16v3.5h-5.5l-.8 3H9l.8-3H6.5L6 13H3z"/><path d="M19 8l2-1.5V10"/></svg>',
    "drug offense": '<svg viewBox="0 0 24 24"><rect x="4" y="9" width="16" height="7" rx="3.5" transform="rotate(-30 12 12.5)"/><path d="M9 10.2l5.5 3.3"/></svg>',
    "other": '<svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/></svg>'
  };
  function renderCrimeTiles(rows) {
    var byCrime = {};
    ALL_CRIMES.forEach(function (k) { byCrime[k] = 0; });
    filtered("crime").forEach(function (r) { if (r.crime_type in byCrime) byCrime[r.crime_type] += 1; });
    var crimes = ALL_CRIMES;
    document.getElementById("chart-crime").innerHTML = crimes.map(function (k) {
      var sel = fCrime.value === k ? " selected" : (fCrime.value ? " faded" : "");
      return '<button class="tile' + sel + '" data-crime="' + esc(k) + '">' +
        (ICONS[k] || ICONS.other) +
        '<span><span class="t-n">' + byCrime[k] + '</span><br><span class="t-l">' + esc(k) + "</span></span></button>";
    }).join("");
    document.querySelectorAll(".tile").forEach(function (b) {
      b.addEventListener("click", function () {
        var k = b.getAttribute("data-crime");
        fCrime.value = fCrime.value === k ? "" : k;
        shown = PAGE; render();
      });
    });
  }

  // --- choropleth map ---
  var STATES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split(" ");
  var RAMP = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"];
  var BREAKS = [1, 5, 15, 30, 60, 100];  // min count for each ramp step
  function rampColor(n) {
    if (!n) return "#e9eef5";
    var c = RAMP[0];
    for (var i = 0; i < BREAKS.length; i++) if (n >= BREAKS[i]) c = RAMP[i];
    return c;
  }
  var tip = document.getElementById("map-tip");
  var mapWired = false;
  function renderMap(rows) {
    var byState = {};
    filtered("state").forEach(function (r) { if (r.state) byState[r.state] = (byState[r.state] || 0) + 1; });
    STATES.forEach(function (code) {
      var els = document.querySelectorAll(".usmap path." + code.toLowerCase() + ", .usmap circle." + code.toLowerCase());
      var n = byState[code] || 0;
      els.forEach(function (el) {
        el.style.fill = rampColor(n);
        el.classList.add("hit");
        el.classList.toggle("selected", fState.value === code);
        if (!mapWired) {
          el.addEventListener("mousemove", function (e) {
            var cnt = (function () { var m = {}; filtered("state").forEach(function (r) { if (r.state) m[r.state] = (m[r.state] || 0) + 1; }); return m[code] || 0; })();
            tip.textContent = code + ": " + cnt + " case" + (cnt === 1 ? "" : "s");
            tip.style.display = "block";
            tip.style.left = (e.clientX + 14) + "px";
            tip.style.top = (e.clientY - 10) + "px";
          });
          el.addEventListener("mouseleave", function () { tip.style.display = "none"; });
          el.addEventListener("click", function () {
            fState.value = fState.value === code ? "" : code;
            shown = PAGE; render();
          });
        }
      });
    });
    mapWired = true;
    document.getElementById("map-legend").innerHTML =
      '<span>0</span><span class="sw" style="background:#e9eef5"></span>' +
      RAMP.map(function (c, i) {
        return '<span class="sw" style="background:' + c + '" title="' + BREAKS[i] + '+"></span>';
      }).join("") + "<span>" + BREAKS[BREAKS.length - 1] + "+ cases</span>";
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
  document.getElementById("chart-year").addEventListener("click", function (e) {
    var y = e.target.getAttribute && e.target.getAttribute("data-year");
    if (!y) return;
    fYear.value = fYear.value === y ? "" : y;
    shown = PAGE; render();
  });
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


def _load_usmap() -> str:
    raw = (Path(__file__).parent / "assets" / "us_states.svg").read_text(encoding="utf-8")
    inner = raw[raw.index(">", raw.index("<svg")) + 1:raw.rindex("</svg>")]
    inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)
    inner = re.sub(r"<defs>.*?</defs>", "", inner, flags=re.S)
    return ('<svg class="usmap" viewBox="0 0 959 593" role="img" '
            'aria-label="Cases by state">' + inner + "</svg>")


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
            .replace("__USMAP__", _load_usmap())
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
