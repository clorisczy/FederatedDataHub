const API_BASE = "";

function levelClass(token) {
  if (token === "visible") return "lvl-strong";
  if (token === "redacted" || token === "aggregate_only") return "lvl-mid";
  return "lvl-faint";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

var payload = null;

function currentDataset() {
  var fid = document.getElementById("fileSelect").value;
  if (!payload || !fid) return null;
  for (var i = 0; i < payload.datasets.length; i++) {
    if (payload.datasets[i].file_id === fid) return payload.datasets[i];
  }
  return null;
}

function renderColumns() {
  var list = document.getElementById("columnList");
  var header = document.getElementById("panelHeader");
  var role = document.getElementById("roleSelect").value;
  var ds = currentDataset();
  list.innerHTML = "";
  if (!ds) {
    header.textContent = "No file selected.";
    return;
  }
  header.textContent =
    ds.department +
    " — " +
    ds.file_name +
    " (" +
    ds.columns.length +
    " columns) — highlighting for role: " +
    role;
  ds.columns.forEach(function (col) {
    var token = (col.by_role && col.by_role[role]) || "hidden";
    var li = document.createElement("li");
    li.className = levelClass(token);
    li.innerHTML =
      '<span class="col-name">' +
      escapeHtml(col.name) +
      '</span><span class="col-tag">' +
      escapeHtml(token.replace(/_/g, " ")) +
      "</span>";
    list.appendChild(li);
  });
}

function wirePayload(data) {
  payload = data;
  if (!data.roles || !data.datasets) {
    document.getElementById("visStatus").textContent = "Invalid API response (missing roles or datasets).";
    return;
  }
  var fs = document.getElementById("fileSelect");
  var rs = document.getElementById("roleSelect");
  fs.innerHTML = "";
  data.datasets.forEach(function (ds) {
    var opt = document.createElement("option");
    opt.value = ds.file_id;
    opt.textContent = ds.department + " — " + ds.file_name;
    fs.appendChild(opt);
  });
  rs.innerHTML = "";
  data.roles.forEach(function (r) {
    var opt = document.createElement("option");
    opt.value = r.key;
    opt.textContent = r.label;
    rs.appendChild(opt);
  });
  fs.disabled = false;
  rs.disabled = false;
  fs.addEventListener("change", renderColumns);
  rs.addEventListener("change", renderColumns);
  renderColumns();
}

fetch(API_BASE + "/api/v1/governance/field-visibility")
  .then(function (r) {
    if (!r.ok) {
      return r.text().then(function (t) {
        throw new Error("HTTP " + r.status + ": " + t.slice(0, 400));
      });
    }
    return r.json();
  })
  .then(wirePayload)
  .catch(function (e) {
    document.getElementById("visStatus").textContent =
      "Could not load visibility data. Open this page from the running server (e.g. http://localhost:8080/visibility.html), not as a local file. " +
      String(e.message || e);
    document.getElementById("fileSelect").innerHTML = '<option value="">—</option>';
    document.getElementById("roleSelect").innerHTML = '<option value="">—</option>';
  });
