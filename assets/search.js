// Recherche côté navigateur sur search.json (aucun serveur nécessaire).
(function () {
  var q = document.getElementById("q");
  var fw = document.getElementById("f-web");
  var fm = document.getElementById("f-mail");
  var out = document.getElementById("results");
  if (!q || !out) return;
  var data = [];

  function norm(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  function render() {
    var term = norm(q.value.trim());
    if (!term && !fw.checked && !fm.checked) { out.innerHTML = ""; return; }
    var res = data.filter(function (e) {
      if (fw.checked && !e.w) return false;
      if (fm.checked && !e.m) return false;
      return !term || norm(e.n + " " + e.c + " " + e.v).indexOf(term) !== -1;
    }).slice(0, 50);
    out.innerHTML = res.length ? res.map(function (e) {
      var li = document.createElement("li");
      li.className = "card";
      var h = document.createElement("h3");
      var a = document.createElement("a");
      a.href = e.u; a.textContent = e.n; h.appendChild(a);
      var p = document.createElement("p");
      p.className = "meta"; p.textContent = e.c + " · " + e.v;
      li.appendChild(h); li.appendChild(p);
      return li.outerHTML;
    }).join("") : "<li>Aucun résultat.</li>";
  }

  fetch(window.SITE_SEARCH).then(function (r) { return r.json(); }).then(function (d) {
    data = d;
    [q, fw, fm].forEach(function (el) { el.addEventListener("input", render); el.addEventListener("change", render); });
  });
})();
