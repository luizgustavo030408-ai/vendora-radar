#!/usr/bin/env python3
"""Gera o site do Vendora Radar (Vercel + Supabase) a partir de src/radar.html.

src/radar.html e a mesma app do artefato do Claude. Este script:
- separa estilos/markup do <script> da app
- troca o banco do artefato por um adaptador do Supabase (login + tempo real)
- troca a exportacao do artefato por download direto (Blob)
Saida: dist/index.html e dist/app.js
"""
import pathlib, re, time

ROOT = pathlib.Path(__file__).parent
SRC = (ROOT / "src" / "radar.html").read_text()
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)

SUPABASE_URL = "https://eorlpkwjqjiylvhygshf.supabase.co"
SUPABASE_KEY = "sb_publishable_7se72onl66-8dfudn__xmQ_xpoB_elQ"  # chave publica (RLS protege os dados)

i = SRC.rindex("<script>")
j = SRC.rindex("</script>")
head_and_body = SRC[:i]
app = SRC[i + len("<script>"):j]

# ---- partes do topo: title/links/scripts externos e <style>
m = re.search(r"<style>(.*?)</style>", head_and_body, re.S)
css = m.group(1)
markup = head_and_body[m.end():].strip()

# conta e saida no lugar do seletor "Voce esta usando como"
acct = '''<div class="who" id="acct">
        <span class="eyebrow" id="acctMail"></span>
        <div class="acct-btns"><button type="button" class="btn sm" id="pwBtn">Trocar senha</button><button type="button" class="btn sm" id="outBtn">Sair</button></div>
      </div>'''
markup = markup.replace('<div class="side-foot">', '<div class="side-foot">' + acct, 1)

# ---- app: boot com Supabase
boot_start = app.index("(async () => {\n  if (!window.claude) return;")
app = app[:boot_start] + '''(async () => {
  db = window.__VR_DB;
  if (!db) return;
  db.collection("leads").limit(5000).onSnapshot(snap => { leads = snap.docs.map(d => ({ id: d.id, ...d.data() })); render(); }, () => toast("A lista parou de atualizar. Recarregue a página."));
  db.doc("config/busca").onSnapshot(snap => { config = snap.exists ? snap.data() : {}; render(); });
})();
'''
_a = app.index('  const dl = window.claude ?'); old_dl = app[_a:app.index('\n}\n', _a) + 1]
app = app.replace(old_dl, '''  try { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })); a.download = `vendora-leads-${today()}.csv`; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); toast("Planilha baixada"); } catch { toast("Não foi possível exportar"); }
''')
assert "window.claude" not in app, "sobrou referencia ao artefato"

LOGIN_CSS = '''
.auth { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 16px; background: var(--bg); background-image: radial-gradient(700px 420px at 80% -10%, var(--glow-soft), transparent 70%), radial-gradient(600px 380px at 0% 110%, var(--glow-soft), transparent 70%); }
.auth .card { width: min(400px, 100%); padding: 28px 26px; display: grid; gap: 18px; }
.auth .lg { display: flex; gap: 12px; align-items: center; }
.auth .lg svg { width: 38px; filter: drop-shadow(0 0 10px var(--glow)); }
.auth h1 { margin: 0; font-size: 1.25rem; letter-spacing: -.02em; }
.auth p { margin: 0; color: var(--muted); font-size: .86rem; }
.auth form { display: grid; gap: 14px; }
.auth .btn { justify-content: center; padding: 11px; }
.auth .err { color: var(--bad); font-size: .84rem; min-height: 1.2em; }
.acct-btns { display: flex; gap: 6px; }
.acct-btns .btn { flex: 1; justify-content: center; }
#acctMail { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.boot { position: fixed; inset: 0; display: grid; place-items: center; color: var(--muted); font-size: .9rem; z-index: 49; background: var(--bg); }
'''

LOGO = re.search(r'<svg viewBox="0 0 340 300".*?</svg>', markup, re.S).group(0).replace('id="vA"', 'id="lA"').replace('id="vB"', 'id="lB"').replace("url(#vA)", "url(#lA)").replace("url(#vB)", "url(#lB)")

AUTH_HTML = f'''<div class="boot" id="boot">Carregando…</div>
<div class="auth" id="auth" hidden>
  <div class="card">
    <div class="lg">{LOGO}<div><h1>Vendora Radar</h1><p>Radar comercial da Vendora Labs</p></div></div>
    <form id="loginForm">
      <div class="field"><label for="lEmail">E-mail</label><input id="lEmail" type="email" autocomplete="username" required></div>
      <div class="field"><label for="lPass">Senha</label><input id="lPass" type="password" autocomplete="current-password" required></div>
      <div class="err" id="lErr" role="alert"></div>
      <button class="btn brand" type="submit" id="lBtn">Entrar</button>
      <p>Esqueceu a senha? Peça para o Luiz redefinir.</p>
    </form>
  </div>
</div>'''

AUTH_JS = '''
(() => {
  const SB = supabase.createClient("__URL__", "__KEY__", { auth: { persistSession: true, autoRefreshToken: true } });
  const $ = id => document.getElementById(id);
  const ini = n => String(n || "").split(/\\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("");

  function makeDb() {
    const cache = new Map(); let leadCbs = [], cfgCbs = [], cfg = {};
    const snapLeads = () => ({ docs: [...cache.values()].map(r => ({ id: r.id, data: () => r.data })) });
    const emitLeads = () => leadCbs.forEach(cb => cb(snapLeads()));
    const emitCfg = () => cfgCbs.forEach(cb => cb({ exists: !!cfg.busca, data: () => cfg.busca || {} }));
    async function loadLeads() {
      let from = 0; const all = [];
      for (;;) { const { data, error } = await SB.from("leads").select("id,data").range(from, from + 999); if (error) throw error; all.push(...data); if (data.length < 1000) break; from += 1000; }
      cache.clear(); all.forEach(r => cache.set(r.id, r)); emitLeads();
    }
    async function loadCfg() { const { data, error } = await SB.from("config").select("id,data"); if (error) throw error; cfg = {}; data.forEach(r => cfg[r.id] = r.data); emitCfg(); }
    async function refreshOne(table, id) {
      const { data } = await SB.from(table).select("id,data").eq("id", id).maybeSingle();
      if (!data) return; if (table === "leads") { cache.set(id, data); emitLeads(); } else { cfg[id] = data.data; emitCfg(); }
    }
    async function patchDoc(table, id, d) {
      const { error } = await SB.rpc("patch_doc", { p_table: table, p_id: id, p_patch: d });
      if (error) { const e = new Error(error.message); e.code = /permission|policy|42501/.test(error.message + error.code) ? "invalid_argument" : "error"; throw e; }
      if (table === "leads" && cache.has(id)) { const r = cache.get(id); cache.set(id, { id, data: { ...r.data, ...d } }); emitLeads(); }
      if (table === "config") { cfg[id] = { ...(cfg[id] || {}), ...d }; emitCfg(); }
      refreshOne(table, id);
    }
    async function setDoc(table, id, d) {
      const { error } = await SB.from(table).upsert({ id, data: d });
      if (error) throw new Error(error.message);
      if (table === "leads") { cache.set(id, { id, data: d }); emitLeads(); } else { cfg[id] = d; emitCfg(); }
    }
    let started = false;
    function start() {
      if (started) return; started = true;
      SB.channel("vr-live")
        .on("postgres_changes", { event: "*", schema: "public", table: "leads" }, p => { if (p.eventType === "DELETE") cache.delete(p.old.id); else cache.set(p.new.id, { id: p.new.id, data: p.new.data }); emitLeads(); })
        .on("postgres_changes", { event: "*", schema: "public", table: "config" }, p => { if (p.eventType !== "DELETE") { cfg[p.new.id] = p.new.data; emitCfg(); } })
        .subscribe();
      // rede de seguranca: recarrega ao voltar para a aba
      document.addEventListener("visibilitychange", () => { if (!document.hidden) { loadLeads().catch(() => {}); loadCfg().catch(() => {}); } });
      window.addEventListener("focus", () => { loadLeads().catch(() => {}); });
      window.addEventListener("online", () => { loadLeads().catch(() => {}); loadCfg().catch(() => {}); });
      // garantia extra: confere o banco a cada 15 s com a aba aberta, mesmo se o tempo real cair
      setInterval(() => { if (!document.hidden) { loadLeads().catch(() => {}); loadCfg().catch(() => {}); } }, 15000);
    }
    const leadsCol = {
      limit() { return leadsCol; },
      doc: id => ({ update: d => patchDoc("leads", id, d), set: d => setDoc("leads", id, d) }),
      onSnapshot(cb, err) { leadCbs.push(cb); start(); loadLeads().catch(e => err && err(e)); }
    };
    return {
      collection: () => leadsCol,
      doc(path) { const [t, id] = path.split("/"); return { update: d => patchDoc(t, id, d), set: d => setDoc(t, id, d), onSnapshot(cb) { cfgCbs.push(cb); start(); loadCfg().catch(() => {}); } }; }
    };
  }

  function showLogin(msg) { $("boot").hidden = true; $("auth").hidden = false; $("lErr").textContent = msg || ""; setTimeout(() => $("lEmail").focus(), 50); }

  async function enter(session) {
    const email = session.user.email;
    const { data: m, error } = await SB.from("membros").select("email,socio,nome,papel,chave").ilike("email", email).maybeSingle();
    if (error || !m) { await SB.auth.signOut(); return showLogin("Este e-mail não tem acesso ao Vendora Radar."); }
    window.VR_ROLE = { socio: m.socio === "joao" ? "joao" : "luiz", nome: m.nome, papel: m.papel || "socio", chave: m.chave, ini: ini(m.nome) };
    window.__VR_DB = makeDb();
    $("auth").hidden = true;
    const parts = __PARTS__; let n = 0;
    const next = () => { if (n >= parts.length) { $("boot").hidden = true; $("acctMail").textContent = email; return; } const s = document.createElement("script"); s.src = parts[n++] + "?v=__V__"; s.onload = next; s.onerror = () => { $("boot").textContent = "Não foi possível carregar o Radar. Recarregue a página."; }; document.body.appendChild(s); };
    next();
  }

  $("loginForm").addEventListener("submit", async ev => {
    ev.preventDefault(); $("lErr").textContent = ""; $("lBtn").disabled = true; $("lBtn").textContent = "Entrando…";
    const { data, error } = await SB.auth.signInWithPassword({ email: $("lEmail").value.trim(), password: $("lPass").value });
    $("lBtn").disabled = false; $("lBtn").textContent = "Entrar";
    if (error) return showLogin(/invalid/i.test(error.message) ? "E-mail ou senha incorretos." : "Não foi possível entrar: " + error.message);
    enter(data.session);
  });

  document.addEventListener("click", async e => {
    const t = e.target.closest("button"); if (!t) return;
    if (t.id === "outBtn") { await SB.auth.signOut(); location.hash = ""; location.reload(); }
    if (t.id === "pwBtn") {
      const modal = $("modal"); modal.hidden = false;
      modal.innerHTML = `<form class="card" id="pwForm" style="width:min(420px,100%)"><div class="card-h"><div><h2>Trocar senha</h2><p class="hsub">Use pelo menos 8 caracteres.</p></div></div><div class="card-b form-grid"><div class="field full"><label for="pw1">Nova senha</label><input id="pw1" type="password" autocomplete="new-password" minlength="8" required></div><div class="field full"><label for="pw2">Repita a nova senha</label><input id="pw2" type="password" autocomplete="new-password" minlength="8" required></div><div class="err full" id="pwErr" style="color:var(--bad);font-size:.84rem"></div><div class="full" style="display:flex;gap:8px;justify-content:flex-end"><button class="btn" type="button" id="pwCancel">Cancelar</button><button class="btn brand" type="submit">Salvar senha</button></div></div></form>`;
      $("pw1").focus(); $("pwCancel").onclick = () => modal.hidden = true;
      $("pwForm").onsubmit = async ev => { ev.preventDefault(); if ($("pw1").value !== $("pw2").value) { $("pwErr").textContent = "As senhas não são iguais."; return; }
        const { error } = await SB.auth.updateUser({ password: $("pw1").value });
        if (error) { $("pwErr").textContent = "Não foi possível trocar: " + error.message; return; }
        modal.hidden = true; const tt = $("toast"); tt.textContent = "Senha alterada"; tt.hidden = false; setTimeout(() => tt.hidden = true, 2400); };
    }
  });

  SB.auth.getSession().then(({ data }) => data.session ? enter(data.session) : showLogin());
})();
'''

V = str(int(time.time()))
index = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#FFFFFF">
<meta name="robots" content="noindex,nofollow">
<script>try{{if(localStorage.getItem("vr_mode")==="dark")document.documentElement.setAttribute("data-vr","dark")}}catch(e){{}}</script>
<title>Vendora Radar</title>
<link rel="icon" href="data:image/svg+xml,{LOGO.replace('"', "'").replace('#', '%23').replace(chr(10), ' ')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js"></script>
<style>{css}{LOGIN_CSS}</style>
</head>
<body>
'''
# markup sem as tags de head que ja estao acima
body = re.sub(r'^.*?(?=<div class="app">)', '', markup, flags=re.S)
index += AUTH_HTML + "\n" + body + "\n<script>" + AUTH_JS.replace("__URL__", SUPABASE_URL).replace("__KEY__", SUPABASE_KEY).replace("__V__", V) + "</script>\n</body>\n</html>\n"

# a app e dividida em partes (scripts classicos compartilham o escopo global)
lines = app.split("\n")
starts = [k for k, l in enumerate(lines) if re.match(r"^(function |async function |const |let |/\* -|document\.|window\.|if \(window\.Chart|\(async)", l)]
chunks, cur, size, last = [], 0, 0, 0
for k in starts:
    seg = sum(len(x) + 1 for x in lines[last:k])
    if size + seg > 24000 and size > 0:
        chunks.append("\n".join(lines[cur:last])); cur, size = last, 0
    size += seg; last = k
chunks.append("\n".join(lines[cur:]))
names = [f"js/a{n}.js" for n in range(len(chunks))]
index = index.replace("__PARTS__", "[" + ",".join(f'"{x}"' for x in names) + "]")
index = index.replace("<style>" + css + LOGIN_CSS + "</style>", '<link rel="stylesheet" href="style.css?v=' + V + '">')
(DIST / "js").mkdir(exist_ok=True)
for x in (DIST / "js").glob("*.js"): x.unlink()
for nm, c in zip(names, chunks): (DIST / nm).write_text(c + "\n")
(DIST / "style.css").write_text(css + LOGIN_CSS)
(DIST / "index.html").write_text(index)
print("ok", len(index), len(app))
