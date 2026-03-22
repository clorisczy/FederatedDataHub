const API_BASE = "";

function token() {
  return localStorage.getItem("muni_hub_token") || "";
}

function authHeaders() {
  var h = {};
  var t = token();
  if (t) h.Authorization = "Bearer " + t;
  return h;
}

async function doUpload(endpoint, fileInputId, outId) {
  var inp = document.getElementById(fileInputId);
  var out = document.getElementById(outId);
  out.textContent = "…";
  if (!inp.files || !inp.files[0]) {
    out.textContent = "Choose a CSV file first.";
    return;
  }
  var fd = new FormData();
  fd.append("file", inp.files[0]);
  var res = await fetch(API_BASE + endpoint, {
    method: "POST",
    headers: authHeaders(),
    body: fd,
  });
  var text = await res.text();
  try {
    out.textContent = JSON.stringify(JSON.parse(text), null, 2);
  } catch (e) {
    out.textContent = text;
  }
}

document.getElementById("btnHealth").addEventListener("click", function () {
  doUpload("/api/v1/data/upload/health", "fileHealth", "outHealth").catch(function (e) {
    document.getElementById("outHealth").textContent = String(e);
  });
});
document.getElementById("btnDrainage").addEventListener("click", function () {
  doUpload("/api/v1/data/upload/drainage", "fileDrainage", "outDrainage").catch(function (e) {
    document.getElementById("outDrainage").textContent = String(e);
  });
});
document.getElementById("btnPlanning").addEventListener("click", function () {
  doUpload("/api/v1/data/upload/planning", "filePlanning", "outPlanning").catch(function (e) {
    document.getElementById("outPlanning").textContent = String(e);
  });
});
