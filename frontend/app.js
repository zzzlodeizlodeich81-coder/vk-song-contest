const state = {
  vkId: localStorage.getItem("vkId") || "",
  name: localStorage.getItem("vkName") || "",
  page: "catalog",
  me: null,
  tracks: [],
  current: null,
  offer: "",
  error: "",
};
const $ = (s) => document.querySelector(s);
const appEl = document.getElementById("app");
async function api(path, opts = {}) {
  const headers = Object.assign(
    { "X-User-Id": state.vkId, "X-User-Name": state.name || `id${state.vkId}` },
    opts.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    opts.headers || {}
  );
  const res = await fetch(path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.message || res.statusText);
  return data;
}
function bar(label, cls, value, max) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0;
  return `<span>${label}</span><div class="bar ${cls}"><i style="width:${pct}%"></i></div><b>${value}</b>`;
}
function statusBadge(st) {
  return `<span class="badge ${st}">${st === "active" ? "в голосовании" : st === "pending" ? "нужны 3 оценки" : st}</span>`;
}
function render() {
  if (!state.vkId) {
    appEl.innerHTML = `
      <div class="wrap login card">
        <h1>Конкурс треков</h1>
        <p class="muted">Вход для пробы. Во ВК id подтянется сам.</p>
        <label>Числовой id</label>
        <input id="inId" placeholder="1001" />
        <label>Имя</label>
        <input id="inName" placeholder="Макс" />
        <button id="go">Войти</button>
      </div>`;
    $("#go").onclick = () => {
      const id = $("#inId").value.trim();
      if (!/^[0-9]{1,16}$/.test(id)) return alert("Только цифры");
      state.vkId = id;
      state.name = $("#inName").value.trim() || `id${id}`;
      localStorage.setItem("vkId", state.vkId);
      localStorage.setItem("vkName", state.name);
      boot();
    };
    return;
  }
  const need = state.me ? state.me.need_ratings : 3;
  appEl.innerHTML = `
    <div class="wrap">
      <header>
        <div>
          <h1>Конкурс треков</h1>
          <div class="muted">${state.name} · id ${state.vkId} · осталось оценок: ${need}</div>
        </div>
        <nav>
          <button class="ghost" data-go="catalog">Каталог</button>
          <button class="ghost" data-go="upload">Мой трек</button>
          <button class="ghost" id="out">Сменить id</button>
        </nav>
      </header>
      <div id="err" class="err">${state.error}</div>
      <div id="page"></div>
    </div>`;
  document.querySelectorAll("[data-go]").forEach((b) => (b.onclick = () => { state.page = b.dataset.go; renderPage(); }));
  $("#out").onclick = () => { localStorage.clear(); state.vkId = ""; location.reload(); };
  renderPage();
}
function renderPage() {
  const page = $("#page");
  state.error = "";
  if (state.page === "catalog") {
    page.innerHTML = state.tracks.length
      ? state.tracks.map((t) => trackCard(t)).join("")
      : `<div class="card muted">Нет треков в голосовании. Загрузите свой и оцените 3 чужих с другим id.</div>`;
    page.querySelectorAll("[data-open]").forEach((el) => { el.onclick = () => openTrack(el.dataset.open); });
  } else if (state.page === "upload") {
    const mine = (state.me && state.me.tracks[0]) || null;
    page.innerHTML = mine ? ownerCard(mine) : uploadForm();
    bindUpload(mine);
  } else if (state.page === "track" && state.current) {
    page.innerHTML = detailCard(state.current);
    bindDetail(state.current);
  }
}
function trackCard(t) {
  const max = Math.max(10, t.scores.lyrics, t.scores.hook, t.scores.music);
  return `
    <div class="card" data-open="${t.id}" style="cursor:pointer">
      <div class="row">
        <div><b>${esc(t.artist)}</b> — ${esc(t.title)}</div>
        <div><b>${t.scores.total}</b> <span class="muted">сумма</span></div>
      </div>
      <div class="bars">
        ${bar("текст", "lyrics", t.scores.lyrics, max)}
        ${bar("хук", "hook", t.scores.hook, max)}
        ${bar("музыка", "music", t.scores.music, max)}
      </div>
      <div class="muted" style="margin-top:6px">${t.scores.votes} оценок · кто голосовал — скрыто</div>
    </div>`;
}
function uploadForm() {
  return `<div class="card"><h3>Загрузить трек</h3>
    <label>Исполнитель</label><input id="artist" />
    <label>Название</label><input id="title" />
    <label>Файл</label><input id="file" type="file" accept="audio/*" />
    <button id="send">Загрузить</button></div>`;
}
function ownerCard(t) {
  return `<div class="card"><div class="row"><h3>${esc(t.artist)} — ${esc(t.title)}</h3>${statusBadge(t.status)}</div>
    <audio controls src="/api/tracks/${t.id}/audio"></audio>
    <textarea id="lyrics">${esc(t.lyrics || t.lyrics_draft || "")}</textarea>
    <button class="ghost" id="asr">Снять текст</button>
    <button id="saveLyrics">Подтвердить текст</button></div>
    <div class="card"><h3>Оферта</h3><div class="offer">${esc(state.offer)}</div>
    <label class="check"><input type="checkbox" id="c1" /> Все права на трек мои</label>
    <label class="check"><input type="checkbox" id="c2" /> Согласен на сборник</label>
    <label class="check"><input type="checkbox" id="c3" /> 85% мне / 5% организатору / 10% дистрибьютору</label>
    <button id="consent">Принять</button></div>`;
}
function detailCard(t) {
  const max = Math.max(10, t.scores.lyrics, t.scores.hook, t.scores.music);
  const voted = t.my_vote;
  return `<div class="card"><button class="ghost" data-go="catalog">←</button>
    <h3>${esc(t.artist)} — ${esc(t.title)}</h3>
    <audio id="player" controls src="/api/tracks/${t.id}/audio"></audio>
    <div class="muted">Прослушано: ${t.my_listen_sec} сек / 45</div>
    <div class="bars">${bar("текст", "lyrics", t.scores.lyrics, max)}${bar("хук", "hook", t.scores.hook, max)}${bar("музыка", "music", t.scores.music, max)}</div>
    <p>Сумма: <b>${t.scores.total}</b></p>
    ${t.lyrics ? `<pre class="offer">${esc(t.lyrics)}</pre>` : ""}</div>
    ${t.owner ? `<div class="card muted">Свой трек оценивать нельзя.</div>` : voted ? `<div class="card">Оценка принята.</div>` : `<div class="card">
      <label>Текст <span id="lv">7</span></label><input class="range" id="lyrics" type="range" min="1" max="10" value="7" />
      <label>Хук <span id="hv">7</span></label><input class="range" id="hook" type="range" min="1" max="10" value="7" />
      <label>Музыка <span id="mv">7</span></label><input class="range" id="music" type="range" min="1" max="10" value="7" />
      <button id="vote" ${t.can_vote ? "" : "disabled"}>Оценить</button></div>`}`;
}
function bindUpload(mine) {
  const send = $("#send");
  if (send) send.onclick = async () => {
    const fd = new FormData();
    fd.append("artist", $("#artist").value);
    fd.append("title", $("#title").value);
    const f = $("#file").files[0];
    if (!f) return alert("Файл");
    fd.append("file", f);
    try { await api("/api/tracks", { method: "POST", body: fd }); await boot(); state.page = "upload"; render(); } catch (e) { showErr(e); }
  };
  if (!mine) return;
  $("#asr").onclick = async () => { const r = await api(`/api/tracks/${mine.id}/transcribe`, { method: "POST", body: "{}" }); $("#lyrics").value = r.lyrics_draft; };
  $("#saveLyrics").onclick = async () => { await api(`/api/tracks/${mine.id}/lyrics`, { method: "POST", body: JSON.stringify({ lyrics: $("#lyrics").value }) }); await boot(); state.page = "upload"; render(); };
  $("#consent").onclick = async () => { await api(`/api/tracks/${mine.id}/consent`, { method: "POST", body: JSON.stringify({ rights_ok: $("#c1").checked, publish_ok: $("#c2").checked, split_ok: $("#c3").checked }) }); await boot(); state.page = "upload"; render(); };
}
function bindDetail(t) {
  document.querySelector("[data-go]")?.addEventListener("click", () => { state.page = "catalog"; renderPage(); });
  const player = $("#player");
  if (player && !t.owner) {
    player.addEventListener("ended", async () => {
      await api(`/api/tracks/${t.id}/listen`, { method: "POST", body: JSON.stringify({ seconds: Math.max(45, Math.floor(player.duration || 45)) }) });
      state.current = await api(`/api/tracks/${t.id}`); renderPage();
    });
    setInterval(async () => {
      if (!player.currentTime) return;
      try { await api(`/api/tracks/${t.id}/listen`, { method: "POST", body: JSON.stringify({ seconds: Math.floor(player.currentTime) }) }); } catch (_) {}
    }, 5000);
  }
  ["lyrics", "hook", "music"].forEach((k) => { const el = document.getElementById(k); if (el) el.oninput = () => { document.getElementById(k[0] + "v").textContent = el.value; }; });
  const vote = $("#vote");
  if (vote) vote.onclick = async () => {
    await api(`/api/tracks/${t.id}/vote`, { method: "POST", body: JSON.stringify({ lyrics: +$("#lyrics").value, hook: +$("#hook").value, music: +$("#music").value }) });
    await boot(); state.current = await api(`/api/tracks/${t.id}`); state.page = "track"; render();
  };
}
async function openTrack(id) { state.current = await api(`/api/tracks/${id}`); state.page = "track"; render(); }
function showErr(e) { state.error = e.message; const box = $("#err"); if (box) box.textContent = state.error; else alert(state.error); }
function esc(s) { return String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&", "<": "<", ">": ">", '"': """, "'": "&#39;" }[c])); }
async function boot() {
  try {
    state.me = await api("/api/me");
    state.tracks = (await api("/api/tracks")).items;
    state.offer = (await api("/api/offer")).markdown;
    render();
  } catch (e) { render(); showErr(e); }
}
if (state.vkId) boot(); else render();
