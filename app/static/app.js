// Small progressive enhancements. Every page works without this file.
(function () {
  // Confirm destructive actions.
  document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // Close the quick-add menu when tapping elsewhere.
  document.addEventListener("click", function (e) {
    document.querySelectorAll("details.quick[open]").forEach(function (d) {
      if (!d.contains(e.target)) d.removeAttribute("open");
    });
  });

  // Payment form: picking a tenant fills the property and a suggested amount.
  var lease = document.getElementById("f-lease_id");
  if (lease) {
    var prop = document.getElementById("f-property_id");
    var amount = document.getElementById("f-amount");
    var kinds = document.querySelectorAll("input[name=kind]");
    var monthField = document.getElementById("month-field");
    var touched = amount && amount.value !== "";
    if (amount) amount.addEventListener("input", function () { touched = true; });
    function currentKind() {
      var k = "rent";
      kinds.forEach(function (r) { if (r.checked) k = r.value; });
      return k;
    }
    function sync() {
      var opt = lease.options[lease.selectedIndex];
      var k = currentKind();
      if (monthField) monthField.hidden = !(k === "rent" || k === "hap" || k === "late_fee");
      if (!opt || !opt.value) return;
      if (prop && opt.dataset.property) prop.value = opt.dataset.property;
      if (amount && !touched) {
        var rent = parseInt(opt.dataset.rent || "0", 10), hap = parseInt(opt.dataset.hap || "0", 10);
        var cents = k === "hap" ? hap : k === "rent" ? rent - hap : 0;
        amount.value = cents > 0 ? (cents / 100).toFixed(2) : "";
      }
    }
    lease.addEventListener("change", sync);
    kinds.forEach(function (r) { r.addEventListener("change", sync); });
    sync();
  }

  // Expense form: show what the chosen category covers.
  var cat = document.getElementById("f-category");
  var hint = document.getElementById("cat-hint");
  if (cat && hint) {
    var show = function () {
      var o = cat.options[cat.selectedIndex];
      hint.textContent = (o && o.dataset.hint) || "";
    };
    cat.addEventListener("change", show);
    show();
  }

  // Lease form: show Section 8 fields only when ticked.
  var s8 = document.getElementById("f-section8");
  var s8box = document.getElementById("s8-fields");
  if (s8 && s8box) {
    var t = function () { s8box.hidden = !s8.checked; };
    s8.addEventListener("change", t);
    t();
  }

  // Mortgage form: switching property reloads last month's split.
  var mp = document.getElementById("f-mortgage-property");
  if (mp) mp.addEventListener("change", function () {
    var i = document.getElementById("f-interest");
    if (i && i.value === "") window.location = "?property_id=" + encodeURIComponent(mp.value);
  });
})();
