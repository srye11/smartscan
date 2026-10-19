(function () {
  const C = window.CONFIG;
  const sb = window.supabase.createClient(C.SUPABASE_URL, C.SUPABASE_ANON_KEY);
  const $ = (id) => document.getElementById(id);

  const BIG9 = ["Milk", "Egg", "Peanut", "Tree Nut", "Soy", "Wheat", "Fish", "Shellfish", "Sesame"];
  const NAV = [
    { id: "scan", label: "Scan label", short: "Scan", ic: "📷" },
    { id: "history", label: "Scan history", short: "History", ic: "🕘" },
    { id: "recipes", label: "Safe recipes", short: "Recipes", ic: "🍽️" },
    { id: "profile", label: "Allergy profile", short: "Profile", ic: "⚙️" },
  ];

  const state = { profile: null, user: null, file: null, signupAllergies: new Set(), profAllergies: new Set(), mode: "signup", recFilter: "All" };

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const show = (el, on) => el.classList.toggle("hidden", !on);
  function msg(el, text, kind) { el.className = "msg " + kind; el.textContent = text; show(el, !!text); }

  // ---------- API ----------
  async function api(path, opts = {}) {
    const { data } = await sb.auth.getSession();
    const token = data.session && data.session.access_token;
    const res = await fetch(C.API_URL + path, {
      ...opts,
      headers: { ...(opts.headers || {}), Authorization: "Bearer " + token },
    });
    if (res.status === 401) { await sb.auth.signOut(); throw new Error("Your login expired. Please log in again."); }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || "Something went wrong (" + res.status + ")");
    return body;
  }

  // ---------- allergy chips ----------
  function drawChips(container, set) {
    container.innerHTML = "";
    BIG9.forEach((a) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip" + (set.has(a) ? " on" : "");
      b.innerHTML = "<span>" + esc(a) + '</span><span class="tick">' + (set.has(a) ? "✓" : "") + "</span>";
      b.onclick = () => { set.has(a) ? set.delete(a) : set.add(a); drawChips(container, set); };
      container.appendChild(b);
    });
  }

  // ---------- auth screen ----------
  function setMode(mode) {
    state.mode = mode;
    const su = mode === "signup";
    $("tabSignup").classList.toggle("on", su);
    $("tabLogin").classList.toggle("on", !su);
    show($("nameRow"), su);
    show($("allergyRow"), su);
    $("authTitle").textContent = su ? "Create your account" : "Welcome back";
    $("authSub").textContent = su ? "Start scanning safely in under 2 minutes" : "Log in to see your profile and scan history";
    $("authBtn").textContent = su ? "Get started, it's free" : "Log in";
    $("password").autocomplete = su ? "new-password" : "current-password";
    msg($("authMsg"), "", "err");
  }
  $("tabSignup").onclick = () => setMode("signup");
  $("tabLogin").onclick = () => setMode("login");

  $("authForm").onsubmit = async (e) => {
    e.preventDefault();
    const email = $("email").value.trim();
    const password = $("password").value;
    const btn = $("authBtn");
    btn.disabled = true;
    msg($("authMsg"), "", "err");
    try {
      if (state.mode === "signup") {
        const name = $("fullName").value.trim();
        if (!name) throw new Error("Please enter your full name.");
        if (state.signupAllergies.size === 0) throw new Error("Pick at least one allergy so the scanner knows what to look for.");
        const { data, error } = await sb.auth.signUp({ email, password, options: { data: { full_name: name } } });
        if (error) throw error;
        if (!data.session) {
          msg($("authMsg"), "Account created. Check your email to confirm it, then log in.", "info");
          return;
        }
        // logged in straight away; save the profile
        await api("/profile", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ full_name: name, allergies: [...state.signupAllergies] }),
        });
      } else {
        const { error } = await sb.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
      await enterApp();
    } catch (err) {
      msg($("authMsg"), err.message || String(err), "err");
    } finally {
      btn.disabled = false;
    }
  };

  // ---------- app shell ----------
  function buildNav() {
    const side = $("sideNav"), bot = $("bottomNav");
    side.innerHTML = ""; bot.innerHTML = "";
    NAV.forEach((n) => {
      const a = document.createElement("button");
      a.dataset.id = n.id; a.textContent = n.ic + "  " + n.label;
      a.onclick = () => go(n.id);
      side.appendChild(a);
      const b = document.createElement("button");
      b.dataset.id = n.id; b.innerHTML = '<span class="ic">' + n.ic + "</span>" + esc(n.short);
      b.onclick = () => go(n.id);
      bot.appendChild(b);
    });
  }

  function go(id) {
    NAV.forEach((n) => show($("v-" + n.id), n.id === id));
    document.querySelectorAll("#sideNav button, #bottomNav button").forEach((b) => b.classList.toggle("on", b.dataset.id === id));
    if (id === "history") loadHistory();
    if (id === "recipes") drawRecipes();
    if (id === "profile") loadProfileForm();
    window.scrollTo(0, 0);
  }

  async function enterApp() {
    const { data } = await sb.auth.getUser();
    state.user = data.user;
    state.profile = await api("/profile");
    const name = state.profile.full_name || (state.user.email || "").split("@")[0];
    $("whoName").textContent = name;
    $("whoEmail").textContent = state.user.email;
    $("avatar").textContent = (name[0] || "?").toUpperCase();
    show($("boot"), false); show($("auth"), false); show($("app"), true);
    buildNav();
    resetScan();
    go(state.profile.allergies && state.profile.allergies.length ? "scan" : "profile");
  }

  async function logout() {
    await sb.auth.signOut();
    state.profile = null;
    show($("app"), false); show($("auth"), true);
  }
  $("logoutSide").onclick = logout;
  $("logoutTop").onclick = logout;

  // ---------- scan ----------
  function resetScan() {
    state.file = null;
    state.originalFile = null;
    show($("cropRow"), false); show($("cropReset"), false);
    $("cropBtn").textContent = "✂️ Crop (optional)";
    show($("preview"), false); show($("dzEmpty"), true); show($("scanline"), false);
    $("scanBtn").disabled = true;
    ["st1", "st2", "st3"].forEach((s, i) => { $(s).className = ""; $(s).firstChild.textContent = String(i + 1); });
    $("resultBody").innerHTML = '<p style="color:var(--muted)">Your results will show here.</p>';
    msg($("scanMsg"), "", "err");
  }

  function pickFile(f) {
    if (!f) return;
    resetScan();
    state.file = f;
    state.originalFile = f;
    const url = URL.createObjectURL(f);
    $("preview").src = url;
    show($("preview"), true); show($("dzEmpty"), false);
    show($("cropRow"), true);
    $("st1").className = "done"; $("st1").firstChild.textContent = "✓";
    $("scanBtn").disabled = false;
  }
  $("camInput").onchange = (e) => { pickFile(e.target.files[0]); e.target.value = ""; };
  $("fileInput").onchange = (e) => { pickFile(e.target.files[0]); e.target.value = ""; };

  // ---------- optional crop ----------
  // The user can crop the photo to just the ingredient list before scanning. It is only an option:
  // if they never press Crop, the original photo is scanned exactly as before.
  let cropper = null;
  let cropUrl = null;

  // Draw the photo on a canvas first, so the browser applies the phone's rotation once,
  // then the crop tool works on a correctly rotated picture.
  function normalisedImageUrl(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        const max = 3000;
        const scale = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
        const c = document.createElement("canvas");
        c.width = Math.max(1, Math.round(img.naturalWidth * scale));
        c.height = Math.max(1, Math.round(img.naturalHeight * scale));
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        c.toBlob((b) => (b ? resolve(URL.createObjectURL(b)) : reject(new Error("Could not open this photo for cropping."))), "image/jpeg", 0.92);
      };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Could not open this photo for cropping.")); };
      img.src = url;
    });
  }

  function closeCrop() {
    if (cropper) { cropper.destroy(); cropper = null; }
    if (cropUrl) { URL.revokeObjectURL(cropUrl); cropUrl = null; }
    $("cropImg").removeAttribute("src");
    show($("cropModal"), false);
    document.body.style.overflow = "";
  }

  async function openCrop() {
    if (!state.originalFile) return;
    if (!window.Cropper) {
      msg($("scanMsg"), "The crop tool could not load. Check your connection and refresh the page. You can still scan the whole photo.", "err");
      return;
    }
    msg($("scanMsg"), "", "err");
    try {
      cropUrl = await normalisedImageUrl(state.originalFile);
    } catch (err) {
      msg($("scanMsg"), err.message || "Could not open the crop tool.", "err");
      return;
    }
    const img = $("cropImg");
    img.onload = () => {
      if (cropper) cropper.destroy();
      cropper = new window.Cropper(img, {
        viewMode: 1,
        dragMode: "crop",
        autoCropArea: 0.9,
        background: false,
        checkOrientation: false,
        scalable: false,
        toggleDragModeOnDblclick: false,
      });
    };
    img.src = cropUrl;
    show($("cropModal"), true);
    document.body.style.overflow = "hidden";
  }

  $("cropBtn").onclick = openCrop;
  $("cropCancel").onclick = closeCrop;
  $("cropRotate").onclick = () => { if (cropper) cropper.rotate(90); };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("cropModal").classList.contains("hidden")) closeCrop();
  });

  $("cropApply").onclick = () => {
    if (!cropper) return;
    const canvas = cropper.getCroppedCanvas({ maxWidth: 3000, maxHeight: 3000, imageSmoothingQuality: "high", fillColor: "#fff" });
    if (!canvas) { msg($("scanMsg"), "Please draw a crop box first.", "err"); return; }
    canvas.toBlob((blob) => {
      if (!blob) { msg($("scanMsg"), "Could not crop this photo. You can still scan the whole photo.", "err"); closeCrop(); return; }
      state.file = new File([blob], "cropped-label.jpg", { type: "image/jpeg" });
      $("preview").src = URL.createObjectURL(state.file);
      show($("cropReset"), true);
      $("cropBtn").textContent = "✂️ Crop again";
      closeCrop();
    }, "image/jpeg", 0.92);
  };

  $("cropReset").onclick = () => {
    if (!state.originalFile) return;
    state.file = state.originalFile;
    $("preview").src = URL.createObjectURL(state.originalFile);
    show($("cropReset"), false);
    $("cropBtn").textContent = "✂️ Crop (optional)";
  };

  function sevClass(s) { return s === "Moderate" ? "Moderate" : s === "Mild" ? "Mild" : "Severe"; }

  // Map the detector's allergen names (e.g. "milk", "tree nut") to the Big 9 names used by the API.
  function bigName(a) {
    const s = String(a || "").toLowerCase().replace(/s$/, "");
    return BIG9.find((b) => b.toLowerCase() === s || b.toLowerCase().replace(/s$/, "") === s) || null;
  }

  // ---------- report a wrong result ----------
  const REPORT_TYPES = [
    ["false_alarm", "False alarm (flagged, but not there)"],
    ["missed", "Missed (allergen not flagged)"],
    ["wrong_severity", "Wrong severity"],
    ["other", "Something else"],
  ];

  function openReport(box, scanId, preset) {
    preset = preset || {};
    box.innerHTML =
      '<div class="rform"><b>Report a wrong result</b>' +
      '<label class="lbl">What went wrong?</label><select class="input r-kind">' +
      REPORT_TYPES.map((t) => '<option value="' + t[0] + '"' + (t[0] === (preset.kind || "false_alarm") ? " selected" : "") + ">" + esc(t[1]) + "</option>").join("") +
      '</select><label class="lbl">Which allergen? (optional)</label><select class="input r-allergen"><option value="">Not sure / not applicable</option>' +
      BIG9.map((a) => '<option value="' + a + '"' + (a === preset.allergen ? " selected" : "") + ">" + esc(a) + "</option>").join("") +
      '</select><label class="lbl">Tell us more (optional)</label>' +
      '<textarea class="input r-note" maxlength="500" placeholder="For example: the label says coconut milk, which is not dairy."></textarea>' +
      '<div class="rbtns"><button type="button" class="btn r-send">Send report</button><button type="button" class="btn ghost r-cancel">Cancel</button></div>' +
      '<div class="msg hidden r-msg"></div></div>';
    box.querySelector(".r-cancel").onclick = () => { box.innerHTML = reportLink(); wireReportLink(box, scanId); };
    box.querySelector(".r-send").onclick = async (e) => {
      const btn = e.currentTarget;
      const m = box.querySelector(".r-msg");
      btn.disabled = true;
      try {
        await api("/report", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            scan_id: scanId,
            kind: box.querySelector(".r-kind").value,
            allergen: box.querySelector(".r-allergen").value || null,
            note: box.querySelector(".r-note").value.trim() || null,
          }),
        });
        box.innerHTML = '<div class="msg ok">Thank you! Your report was saved.</div>';
      } catch (err) {
        msg(m, err.message, "err");
        btn.disabled = false;
      }
    };
  }

  function reportLink() { return '<button type="button" class="rlink-main">⚑ Something wrong? Report this result</button>'; }
  function wireReportLink(box, scanId) {
    const b = box.querySelector(".rlink-main");
    if (b) b.onclick = () => openReport(box, scanId, {});
  }

  function renderResult(r, target, scanId) {
    const flagged = (r && r.flagged_allergens) || [];
    let html;
    if (!flagged.length) {
      html = '<div class="safe">✓ No allergens from your profile were found.</div>' +
        '<p class="note">Always double-check the packaging. SmartScan is a helper, not a medical guarantee.</p>';
    } else {
      html = '<div class="sec">ALLERGENS FOUND</div>';
      flagged.forEach((f, i) => {
        const sev = sevClass(f.severity);
        html += '<div class="res ' + sev + '"><div class="top"><span class="name">' + esc(f.allergen) + '</span><span class="badge">' + esc(sev) + "</span></div>" +
          (f.quoted_text ? '<div class="q">Found: <b>' + esc(f.quoted_text) + "</b></div>" : "") +
          (f.explanation ? '<div class="why">' + esc(f.explanation) + "</div>" : "") +
          (scanId != null ? '<button type="button" class="rlink" data-i="' + i + '">Wrong? Report</button>' : "") + "</div>";
      });
      html += '<p class="note">Severe = listed as an ingredient. Moderate = "may contain" or shared facility warning.</p>';
    }
    if (scanId != null) html += '<div class="reportbox">' + reportLink() + "</div>";
    target.innerHTML = html;
    if (scanId != null) {
      const box = target.querySelector(".reportbox");
      wireReportLink(box, scanId);
      target.querySelectorAll(".rlink").forEach((b) => {
        b.onclick = () => {
          const f = flagged[Number(b.dataset.i)];
          openReport(box, scanId, { kind: "false_alarm", allergen: bigName(f.allergen) });
          box.scrollIntoView({ behavior: "smooth", block: "center" });
        };
      });
    }
  }

  $("scanBtn").onclick = async () => {
    if (!state.file) return;
    const btn = $("scanBtn");
    btn.disabled = true;
    msg($("scanMsg"), "", "err");
    $("st2").className = "on";
    $("st3").className = "";
    $("resultBody").innerHTML = '<p style="color:var(--muted)">Reading the label…</p>';
    show($("scanline"), true);
    const slow = setTimeout(() => msg($("scanMsg"), "The server was asleep and is waking up. This can take up to a minute the first time.", "info"), 8000);
    try {
      const fd = new FormData();
      fd.append("file", state.file);
      const r = await api("/scan", { method: "POST", body: fd });
      $("st2").className = "done"; $("st2").firstChild.textContent = "✓";
      $("st3").className = "done"; $("st3").firstChild.textContent = "✓";
      renderResult(r.allergen_result, $("resultBody"), r.id);
      msg($("scanMsg"), "Saved to your scan history.", "ok");
    } catch (err) {
      $("st2").className = "";
      $("resultBody").innerHTML = '<p style="color:var(--muted)">No result.</p>';
      msg($("scanMsg"), err.message, "err");
    } finally {
      clearTimeout(slow);
      show($("scanline"), false);
      btn.disabled = false;
    }
  };

  // ---------- type ingredients mode ----------
  function setScanMode(mode) {
    state.scanMode = mode;
    const photo = mode === "photo";
    $("modePhotoTab").classList.toggle("on", photo);
    $("modeTextTab").classList.toggle("on", !photo);
    show($("modePhoto"), photo);
    show($("modeText"), !photo);
    $("scanSub").textContent = photo
      ? "Take a photo of the ingredient list. The AI reads it and checks your allergies."
      : "Type or paste the ingredient list. The AI checks it against your allergies.";
    $("st1t").textContent = photo ? "Label photo selected" : "Ingredients entered";
    resetScan();
  }
  $("modePhotoTab").onclick = () => setScanMode("photo");
  $("modeTextTab").onclick = () => setScanMode("text");

  $("textBtn").onclick = async () => {
    const text = $("ingText").value.trim();
    if (text.length < 3) { msg($("scanMsg"), "Type or paste the ingredient list first.", "err"); return; }
    const btn = $("textBtn");
    btn.disabled = true;
    msg($("scanMsg"), "", "err");
    $("st1").className = "done"; $("st1").firstChild.textContent = "✓";
    $("st2").className = "on";
    $("st3").className = "";
    $("resultBody").innerHTML = '<p style="color:var(--muted)">Checking the ingredients…</p>';
    const slow = setTimeout(() => msg($("scanMsg"), "The server was asleep and is waking up. This can take up to a minute the first time.", "info"), 8000);
    try {
      const r = await api("/scan-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      $("st2").className = "done"; $("st2").firstChild.textContent = "✓";
      $("st3").className = "done"; $("st3").firstChild.textContent = "✓";
      renderResult(r.allergen_result, $("resultBody"), r.id);
      msg($("scanMsg"), "Saved to your scan history.", "ok");
    } catch (err) {
      $("st2").className = "";
      $("resultBody").innerHTML = '<p style="color:var(--muted)">No result.</p>';
      msg($("scanMsg"), err.message, "err");
    } finally {
      clearTimeout(slow);
      btn.disabled = false;
    }
  };

  // ---------- history ----------
  async function loadHistory() {
    const box = $("histList");
    box.innerHTML = '<p style="color:var(--muted)">Loading…</p>';
    try {
      const rows = await api("/scans");
      if (!rows.length) { box.innerHTML = '<div class="card">No scans yet. Scan your first label!</div>'; return; }
      box.innerHTML = "";
      rows.forEach((r, i) => {
        const flagged = (r.allergen_result && r.allergen_result.flagged_allergens) || [];
        const d = new Date(r.created_at);
        const card = document.createElement("div");
        card.className = "card hist";
        const tags = flagged.length
          ? flagged.map((f) => '<span class="tag ' + (f.severity === "Moderate" ? "m" : f.severity === "Mild" ? "l" : "s") + '">' + esc(f.allergen) + "</span>").join("")
          : '<span class="tag l">✓ Safe</span>';
        const isText = !r.image_path && r.input_text;
        const thumb = r.image_url ? '<img src="' + esc(r.image_url) + '" alt="Scanned label">'
          : isText ? '<div class="txtthumb">⌨️</div>' : '<img alt="">';
        const snip = isText ? '<div class="snip">Typed: "' + esc(r.input_text.length > 110 ? r.input_text.slice(0, 110) + "…" : r.input_text) + '"</div>' : "";
        card.innerHTML = thumb +
          '<div class="body"><b>Scan ' + (rows.length - i) + (i === 0 ? " (most recent)" : "") + '</b><div class="when">' +
          esc(d.toLocaleString()) + "</div>" + snip + "<div>" + tags + '</div><div class="acts"><button class="view">View result</button><button class="del">Delete</button></div>' +
          '<div class="detail hidden"></div></div>';
        const detail = card.querySelector(".detail");
        card.querySelector(".view").onclick = () => {
          if (detail.classList.contains("hidden")) renderResult(r.allergen_result, detail, r.id);
          detail.classList.toggle("hidden");
        };
        card.querySelector(".del").onclick = async () => {
          if (!confirm("Delete this scan?")) return;
          try { await api("/scans/" + r.id, { method: "DELETE" }); card.remove(); } catch (e) { alert(e.message); }
        };
        box.appendChild(card);
      });
    } catch (err) {
      box.innerHTML = '<div class="msg err">' + esc(err.message) + "</div>";
    }
  }

  // ---------- recipes ----------
  const FILTERS = ["All", "Dairy-free", "Egg-free", "Quick (<30m)", "High protein"];
  function drawRecipes() {
    const mine = new Set((state.profile.allergies || []).map((a) => a.toLowerCase()));
    $("recSub").textContent = mine.size ? "All recipes are free of: " + [...mine].join(", ") + "." : "Add allergies in your profile to filter recipes.";
    const fb = $("recFilters");
    fb.innerHTML = "";
    FILTERS.forEach((f) => {
      const b = document.createElement("button");
      b.textContent = f; b.className = f === state.recFilter ? "on" : "";
      b.onclick = () => { state.recFilter = f; drawRecipes(); };
      fb.appendChild(b);
    });
    const list = window.RECIPES.filter((r) => !r.tags.some((t) => mine.has(t))).filter((r) => {
      const f = state.recFilter;
      if (f === "Dairy-free") return !r.tags.includes("milk");
      if (f === "Egg-free") return !r.tags.includes("egg");
      if (f === "Quick (<30m)") return r.time < 30;
      if (f === "High protein") return r.free.includes("High protein");
      return true;
    });
    const grid = $("recGrid");
    grid.innerHTML = list.length ? "" : '<div class="card">No recipes match. Try another filter.</div>';
    list.forEach((r) => {
      const c = document.createElement("div");
      c.className = "rcard";
      c.innerHTML = '<div class="pic" style="background:' + r.color + '">' + r.emoji + "<span>✓ Safe for you</span></div>" +
        '<div class="rb"><h4>' + esc(r.name) + '</h4><div class="meta">⏱ ' + r.time + " min · " + r.kcal + " kcal · " + esc(r.level) + "</div></div>" +
        '<button class="more">View recipe →</button><div class="rdetail hidden"><b>Ingredients</b><ul>' +
        r.ingredients.map((i) => "<li>" + esc(i) + "</li>").join("") + "</ul><b>Steps</b><ol>" +
        r.steps.map((s) => "<li>" + esc(s) + "</li>").join("") + "</ol></div>";
      c.querySelector(".more").onclick = () => c.querySelector(".rdetail").classList.toggle("hidden");
      grid.appendChild(c);
    });
  }

  // ---------- profile ----------
  function loadProfileForm() {
    state.profAllergies = new Set(state.profile.allergies || []);
    $("profName").value = state.profile.full_name || "";
    drawChips($("profChips"), state.profAllergies);
    msg($("profMsg"), "", "ok");
  }
  $("saveProf").onclick = async () => {
    const btn = $("saveProf");
    btn.disabled = true;
    try {
      state.profile = await api("/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: $("profName").value.trim() || null, allergies: [...state.profAllergies] }),
      });
      $("whoName").textContent = state.profile.full_name || $("whoName").textContent;
      msg($("profMsg"), "Saved.", "ok");
    } catch (err) {
      msg($("profMsg"), err.message, "err");
    } finally { btn.disabled = false; }
  };

  // ---------- start ----------
  drawChips($("signupChips"), state.signupAllergies);
  setMode("signup");
  fetch(C.API_URL + "/health").catch(() => {}); // wake the free server early

  (async function boot() {
    try {
      const { data } = await sb.auth.getSession();
      if (data.session) { await enterApp(); return; }
    } catch (e) { /* fall through to login */ }
    show($("boot"), false); show($("auth"), true);
  })();
})();