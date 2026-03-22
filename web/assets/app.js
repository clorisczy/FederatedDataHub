const API_BASE = "";

let map;
const layers = { med: null, infra: null, zone: null };
let token = localStorage.getItem("muni_hub_token") || "";
let lastScenario = null;
let jsonVisible = false;

function authHeaders() {
  const h = { Accept: "application/json" };
  if (token) h.Authorization = "Bearer " + token;
  return h;
}

function syncJsonPanel() {
  var pre = document.getElementById("jsonPre");
  if (!pre) return;
  if (!lastScenario) {
    pre.textContent = "(Load federated layers first.)";
    return;
  }
  pre.textContent = JSON.stringify(lastScenario, null, 2);
}

function setJsonOpen(open) {
  jsonVisible = open;
  var pre = document.getElementById("jsonPre");
  if (!pre) return;
  if (open) {
    pre.classList.add("open");
    syncJsonPanel();
  } else {
    pre.classList.remove("open");
  }
}

async function issueToken() {
  const role = document.getElementById("roleSelect").value;
  const res = await fetch(API_BASE + "/api/v1/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role: role, sub: "demo-analyst" }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  token = data.access_token;
  localStorage.setItem("muni_hub_token", token);
  document.getElementById("tokenStatus").textContent = "Stored JWT for role: " + data.role;
}

async function loadCatalog() {
  const res = await fetch(API_BASE + "/api/v1/catalog", { headers: authHeaders() });
  const data = await res.json();
  const el = document.getElementById("catalog");
  el.innerHTML = data
    .map(function (d) {
      return (
        "<article><h3>" +
        d.title +
        "</h3><p>" +
        d.description +
        '</p><p><strong>Endpoint:</strong> <code>' +
        d.endpoint +
        "</code></p></article>"
      );
    })
    .join("");
}

async function loadAudit() {
  const res = await fetch(API_BASE + "/api/v1/governance/audit", { headers: authHeaders() });
  const data = await res.json();
  document.getElementById("audit").innerHTML =
    "<pre>" + JSON.stringify(data.entries, null, 2) + "</pre>";
}

function clearLayerGroup(name) {
  if (layers[name]) {
    map.removeLayer(layers[name]);
    layers[name] = null;
  }
}

function addMarkers(groupName, items, color) {
  const g = L.layerGroup();
  items.forEach(function (ev) {
    const sp = ev.spatial;
    const gj = sp && sp.geojson;
    if (!gj || gj.type !== "Point") return;
    const lon = gj.coordinates[0];
    const lat = gj.coordinates[1];
    const m = L.circleMarker([lat, lon], {
      radius: groupName === "zone" ? 5 : 7,
      color: "#0f1419",
      weight: 1,
      fillColor: color,
      fillOpacity: 0.82,
    });
    const body =
      "<strong>" +
      ev.event_type +
      "</strong><br/><span style=\"opacity:.8\">" +
      ev.source_department +
      '</span><br/><pre style="white-space:pre-wrap;margin:6px 0 0;font-size:11px;color:#111">' +
      JSON.stringify(ev.payload, null, 2) +
      "</pre>";
    m.bindPopup('<div style="font-size:12px;max-width:220px;color:#111">' + body + "</div>");
    m.addTo(g);
  });
  g.addTo(map);
  layers[groupName] = g;
}

function roleHintHtml(effectiveRole) {
  var hints = {
    public:
      "<br/><br/><strong style=\"color:#fbbf24\">Public:</strong> health layer has no map points; open <strong>Federated JSON</strong> to compare payloads.",
    dept_public_health:
      "<br/><br/><strong style=\"color:#6ee7b7\">Public Health dept:</strong> full drainage linkage on medical events; planning applicant redacted; full engineering detail.",
    dept_engineering:
      "<br/><br/><strong style=\"color:#93c5fd\">Engineering dept:</strong> full infra internals; health at community centroid; planning address visible, applicant redacted.",
    dept_planning:
      "<br/><br/><strong style=\"color:#fcd34d\">Planning dept:</strong> contacts on your applications; health centroids only; engineering summary (no hierarchy names).",
  };
  return hints[effectiveRole] || "";
}

async function loadScenario() {
  const disease = document.getElementById("diseaseInput").value.trim();
  const year = document.getElementById("yearInput").value;
  const limit = document.getElementById("limitInput").value;
  const params = new URLSearchParams({ limit: limit });
  if (disease) params.set("disease", disease);
  if (year) params.set("year", year);

  const res = await fetch(API_BASE + "/api/v1/federated/scenario?" + params.toString(), {
    headers: authHeaders(),
  });
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  const data = await res.json();
  lastScenario = data;

  document.getElementById("insight").innerHTML =
    '<strong style="color:#e8eef5">Federation narrative</strong><br/>' +
    data.insight.narrative +
    roleHintHtml(data.effective_role);

  if (jsonVisible) syncJsonPanel();

  clearLayerGroup("med");
  clearLayerGroup("infra");
  clearLayerGroup("zone");

  addMarkers("med", data.layers.medical || [], "#f472b6");
  addMarkers("infra", data.layers.infra || [], "#34d399");
  addMarkers("zone", data.layers.zone || [], "#fbbf24");

  const bounds = [];
  ["medical", "infra", "zone"].forEach(function (k) {
    (data.layers[k] || []).forEach(function (ev) {
      const gj = ev.spatial && ev.spatial.geojson;
      if (gj && gj.type === "Point")
        bounds.push([gj.coordinates[1], gj.coordinates[0]]);
    });
  });
  if (bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
}

function initMap() {
  map = L.map("map", { zoomControl: true }).setView([43.4516, -80.4936], 12);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; OSM &copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 20,
  }).addTo(map);
}

document.getElementById("btnToken").addEventListener("click", function () {
  issueToken().catch(function (e) {
    alert(e.message);
  });
});

document.getElementById("btnLoad").addEventListener("click", function () {
  loadScenario().catch(function (e) {
    alert(e.message);
  });
});

var btnJson = document.getElementById("btnJson");
if (btnJson) {
  btnJson.addEventListener("click", function () {
    setJsonOpen(!jsonVisible);
  });
}

initMap();
loadCatalog().catch(console.error);
loadAudit().catch(console.error);
loadScenario().catch(console.error);

if (token) {
  document.getElementById("tokenStatus").textContent =
    "Using token from previous session (localStorage).";
}
