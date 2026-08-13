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
<title>Flock Camera Crime Tracker</title>
<meta name="description" content="A daily-updated database of news stories in which Flock Safety cameras helped solve or prevent a crime.">
<style>
  :root {
    --ground: #fff7ed;
    --card: #fffdf8;
    --ink: #5d4c37;
    --ink-strong: #3f3223;
    --muted: #8a7a64;
    --accent: #d97706;
    --burgundy: #9c4227;
    --teal: #3f7d74;
    --hairline: #e8dcc8;
    --grid: #f0e6d4;
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
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin: 28px 0; }
  .card { background: var(--card); border: 1px solid var(--hairline); border-radius: 10px; padding: 16px 18px; }
  .card .num { font-size: 1.9rem; font-weight: 700; color: var(--ink-strong); }
  .card .lbl { font-size: 0.82rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 28px; }
  @media (max-width: 760px) { .charts { grid-template-columns: 1fr; } }
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
  td.date { white-space: nowrap; font-variant-numeric: tabular-nums; }
  td.loc { white-space: nowrap; }
  td.summary { min-width: 320px; }
  a { color: var(--burgundy); }
  .srclink { font-size: 0.85rem; }
  .pill { display: inline-block; background: #f7ecd9; border-radius: 999px; padding: 1px 9px; font-size: 0.8rem; color: var(--ink); white-space: nowrap; }
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
    <h1>Flock Camera Crime Tracker</h1>
    <p class="subtitle">A daily-updated database of news stories in which Flock Safety cameras helped solve or prevent a crime.</p>
    <p class="updated">Last updated __UPDATED__ &middot; <a class="dl" href="stories.csv" download>Download the full dataset (CSV)</a></p>
  </header>

  <div class="cards" id="cards"></div>

  <div class="charts">
    <div class="chart-card"><h3>Incidents by year</h3><div id="chart-year"></div></div>
    <div class="chart-card"><h3>Most common crime types</h3><div id="chart-crime"></div></div>
  </div>

  <div class="filters">
    <input id="q" type="search" placeholder="Search city, outlet, summary&hellip;" aria-label="Search stories">
    <select id="f-state" aria-label="Filter by state"><option value="">All states</option></select>
    <select id="f-crime" aria-label="Filter by crime type"><option value="">All crime types</option></select>
    <select id="f-year" aria-label="Filter by year"><option value="">All years</option></select>
    <span class="count" id="count"></span>
  </div>

  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Date</th><th>Location</th><th>Crime</th><th>Camera role</th>
        <th>Outcome</th><th>Summary</th><th>Source</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <div class="more" id="more" hidden><button id="more-btn">Show more</button></div>
  </div>

  <section class="method" id="courts-section" hidden>
    <h2>Court records</h2>
    <p class="subtitle" style="font-size:0.95rem">Federal court filings and opinions in which Flock camera evidence figured in a criminal case, found via the <a href="https://www.courtlistener.com/">CourtListener</a>/RECAP archive &mdash; <span id="court-count"></span> records &middot; <a href="court_records.csv" download>Download CSV</a></p>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Filed</th><th>Case</th><th>Court</th><th>Type</th><th>Crime</th><th>Flock's role</th><th>Link</th>
        </tr></thead>
        <tbody id="court-rows"></tbody>
      </table>
    </div>
  </section>

  <section class="method">
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
    <a href="stories.csv">CSV download</a>.</p>
  </section>

  <footer>
    Data collected via GDELT and Google News; classification assisted by Claude.
  </footer>
</div>

<script id="data" type="application/json">__DATA_JSON__</script>
<script id="court-data" type="application/json">__COURT_JSON__</script>
<script>
(function () {
  var ALL = JSON.parse(document.getElementById("data").textContent);
  var PAGE = 100;
  var shown = PAGE;

  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var yearOf = function (r) { return (r.incident_date || r.date_added || "").slice(0, 4); };

  // --- filters ---
  var q = document.getElementById("q");
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

  // --- stat cards ---
  function renderCards(rows) {
    var states = new Set(rows.map(function (r) { return r.state; }).filter(Boolean));
    var thisYear = String(new Date().getFullYear());
    var ty = rows.filter(function (r) { return yearOf(r) === thisYear; }).length;
    var byCrime = {};
    rows.forEach(function (r) { if (r.crime_type) byCrime[r.crime_type] = (byCrime[r.crime_type] || 0) + 1; });
    var top = Object.keys(byCrime).sort(function (a, b) { return byCrime[b] - byCrime[a]; })[0] || "&mdash;";
    document.getElementById("cards").innerHTML =
      '<div class="card"><div class="num">' + rows.length + '</div><div class="lbl">Incidents</div></div>' +
      '<div class="card"><div class="num">' + states.size + '</div><div class="lbl">States</div></div>' +
      '<div class="card"><div class="num">' + ty + '</div><div class="lbl">In ' + thisYear + '</div></div>' +
      '<div class="card"><div class="num" style="font-size:1.15rem;padding-top:10px">' + esc(top) + '</div><div class="lbl">Top crime type</div></div>';
  }

  // --- charts (inline SVG, single amber series, direct value labels) ---
  function barChartV(counts, keys) {
    var W = 480, H = 220, padB = 26, padT = 18, padL = 8, padR = 8;
    var max = Math.max.apply(null, keys.map(function (k) { return counts[k]; }).concat([1]));
    var bw = (W - padL - padR) / keys.length;
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Incidents by year">';
    s += '<line x1="' + padL + '" y1="' + (H - padB) + '" x2="' + (W - padR) + '" y2="' + (H - padB) + '" stroke="#c9b896" stroke-width="1"/>';
    keys.forEach(function (k, i) {
      var v = counts[k];
      var h = Math.round((H - padB - padT) * v / max);
      var x = padL + i * bw + bw * 0.15, w = bw * 0.7;
      var y = H - padB - h;
      s += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + Math.max(h, 1) + '" rx="4" fill="#d97706"/>';
      s += '<text x="' + (x + w / 2) + '" y="' + (y - 5) + '" text-anchor="middle" font-size="11" fill="#5d4c37">' + v + "</text>";
      s += '<text x="' + (x + w / 2) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="11" fill="#8a7a64">' + esc(k) + "</text>";
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
      s += '<text x="' + (labelW - 8) + '" y="' + (y + rowH / 2 + 4) + '" text-anchor="end" font-size="11.5" fill="#5d4c37">' + esc(k) + "</text>";
      s += '<rect x="' + labelW + '" y="' + (y + 4) + '" width="' + w + '" height="' + (rowH - 10) + '" rx="4" fill="#d97706"/>';
      s += '<text x="' + (labelW + w + 6) + '" y="' + (y + rowH / 2 + 4) + '" font-size="11" fill="#5d4c37">' + v + "</text>";
    });
    return s + "</svg>";
  }
  function renderCharts(rows) {
    var byYear = {};
    rows.forEach(function (r) { var y = yearOf(r); if (y) byYear[y] = (byYear[y] || 0) + 1; });
    var years = Object.keys(byYear).sort();
    document.getElementById("chart-year").innerHTML =
      years.length ? barChartV(byYear, years) : '<p style="color:#8a7a64">No data yet.</p>';

    var byCrime = {};
    rows.forEach(function (r) { if (r.crime_type) byCrime[r.crime_type] = (byCrime[r.crime_type] || 0) + 1; });
    var crimes = Object.keys(byCrime).sort(function (a, b) { return byCrime[b] - byCrime[a]; }).slice(0, 8);
    document.getElementById("chart-crime").innerHTML =
      crimes.length ? barChartH(byCrime, crimes) : '<p style="color:#8a7a64">No data yet.</p>';
  }

  // --- table ---
  function sourceCell(r) {
    var links = ['<a class="srclink" href="' + esc(r.source_url) + '" rel="nofollow noopener">' + esc(r.source_name || "link") + "</a>"];
    (r.additional_sources || "").split(" ").filter(Boolean).forEach(function (u, i) {
      links.push('<a class="srclink" href="' + esc(u) + '" rel="nofollow noopener">+' + (i + 2) + "</a>");
    });
    return links.join(" ");
  }
  function renderTable(rows) {
    var body = rows.slice(0, shown).map(function (r) {
      return "<tr>" +
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
      body || '<tr><td colspan="7" style="color:#8a7a64">No matching stories.</td></tr>';
    document.getElementById("count").textContent =
      rows.length + " of " + ALL.length + " incidents";
    document.getElementById("more").hidden = rows.length <= shown;
  }

  function render() {
    var rows = filtered();
    rows.sort(function (a, b) {
      return (b.incident_date || b.date_added) < (a.incident_date || a.date_added) ? -1 : 1;
    });
    renderCards(rows);
    renderCharts(rows);
    renderTable(rows);
  }

  [q, fState, fCrime, fYear].forEach(function (el) {
    el.addEventListener("input", function () { shown = PAGE; render(); });
  });
  document.getElementById("more-btn").addEventListener("click", function () {
    shown += PAGE; render();
  });

  render();

  // --- court records (static list; separate, smaller dataset) ---
  var COURT = JSON.parse(document.getElementById("court-data").textContent);
  if (COURT.length) {
    document.getElementById("courts-section").hidden = false;
    document.getElementById("court-count").textContent = COURT.length;
    document.getElementById("court-rows").innerHTML = COURT.map(function (r) {
      var caseCell = esc(r.case_name) +
        (r.matched_story_id ? ' <span class="pill" title="Linked to a news incident in the table above">news #' + esc(r.matched_story_id) + "</span>" : "");
      return "<tr>" +
        '<td class="date">' + esc(r.date_filed) + "</td>" +
        "<td>" + caseCell + "</td>" +
        "<td>" + esc(r.court) + "</td>" +
        "<td>" + esc(r.record_type) + "</td>" +
        '<td><span class="pill">' + esc(r.crime_type || "—") + "</span></td>" +
        "<td>" + esc(r.flock_role || r.summary) + "</td>" +
        '<td><a class="srclink" href="' + esc(r.source_url) + '" rel="nofollow noopener">docket</a></td>' +
        "</tr>";
    }).join("");
  }
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

    if STORIES_CSV.exists():
        shutil.copy(STORIES_CSV, SITE_DIR / "stories.csv")
    if COURT_CSV.exists():
        shutil.copy(COURT_CSV, SITE_DIR / "court_records.csv")
    print(f"Site built with {len(stories)} stories, {len(courts)} court records "
          f"-> {SITE_DIR / 'index.html'}")


if __name__ == "__main__":
    build_site()
