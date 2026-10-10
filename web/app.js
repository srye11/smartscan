(function () {
  const C = window.CONFIG;
  const sb = window.supabase.createClient(C.SUPABASE_URL, C.SUPABASE_ANON_KEY);
  const $ = (id) => document.getElementById(id);

  const BIG9 = ["Milk", "Egg", "Peanut", "Tree Nut", "Soy", "Wheat", "Fish", "Shellfish", "Sesame"];
  const NAV = [
    { id: "scan", label: "Scan label", ic: "📷" },
    { id: "history", label: "Scan history", ic: "🕘" },
    { id: "recipes", label: "Safe recipes", ic: "🍽️" },
    { id: "profile", label: "Allergy profile", ic: "⚙️" },
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
      b.dataset.id = n.id; b.innerHTML = '<span class="ic">' + n.ic + "</span>" + esc(n.label.split(" ").pop());
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
    show($("preview"), false); show($("dzEmpty"), true); show($("scanline"), false);
    $("scanBtn").disabled = true;
    ["st1", "st2", "st3"].forEach((s) => ($(s).className = ""));
    $("resultBody").innerHTML = '<p style="color:var(--muted)">Your results will show here.</p>';
    msg($("scanMsg"), "", "err");
  }

  function pickFile(f) {
    if (!f) return;
    resetScan();
    state.file = f;
    const url = URL.createObjectURL(f);
    $("preview").src = url;
    show($("preview"), true); show($("dzEmpty"), false);
    $("st1").className = "done"; $("st1").firstChild.textContent = "✓";
    $("scanBtn").disabled = false;
  }
  $("camInput").onchange = (e) => { pickFile(e.target.files[0]); e.target.value = ""; };
  $("fileInput").onchange = (e) => { pickFile(e.target.files[0]); e.target.value = ""; };

  function sevClass(s) { return s === "Moderate" ? "Moderate" : s === "Mild" ? "Mild" : "Severe"; }

  function renderResult(r, target) {
    const flagged = (r && r.flagged_allergens) || [];
    if (!flagged.length) {
      target.innerHTML = '<div class="safe">✓ No allergens from your profile were found on this label.</div>' +
        '<p class="note">Always double-check the packaging. SmartScan is a helper, not a medical guarantee.</p>';
      return;
    }
    let html = '<div class="sec">ALLERGENS FOUND</div>';
    flagged.forEach((f) => {
      const sev = sevClass(f.severity);
      html += '<div class="res ' + sev + '"><div class="top"><span class="name">' + esc(f.allergen) + '</span><span class="badge">' + esc(sev) + "</span></div>" +
        (f.quoted_text ? '<div class="q">Found on label: <b>' + esc(f.quoted_text) + "</b></div>" : "") +
        (f.explanation ? '<div class="why">' + esc(f.explanation) + "</div>" : "") + "</div>";
    });
    html += '<p class="note">Severe = listed as an ingredient. Moderate = "may contain" or shared facility warning.</p>';
    target.innerHTML = html;
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
      renderResult(r.allergen_result, $("resultBody"));
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
        card.innerHTML =
          (r.image_url ? '<img src="' + esc(r.image_url) + '" alt="Scanned label">' : '<img alt="">') +
          '<div class="body"><b>Scan ' + (rows.length - i) + (i === 0 ? " (most recent)" : "") + '</b><div class="when">' +
          esc(d.toLocaleString()) + "</div><div>" + tags + '</div><div class="acts"><button class="view">View result</button><button class="del">Delete</button></div>' +
          '<div class="detail hidden"></div></div>';
        const detail = card.querySelector(".detail");
        card.querySelector(".view").onclick = () => {
          if (detail.classList.contains("hidden")) renderResult(r.allergen_result, detail);
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
