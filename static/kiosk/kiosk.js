/* 뭉클 부스 키오스크 상태 머신
 *
 * 어트랙트 → 알아보기 → 코드 입력 → 도안 선택 → 인쇄 → 대기(미니게임/소개) → 띵동 호출 → 어트랙트
 *
 * - 스테이션 지정: ?station=A (기본 A) — 호출 이벤트는 자기 스테이션만 반응
 * - 호출 인터럽트 최우선: 어떤 화면(미니게임 포함)에서도 called 이벤트가 오면 즉시 오버레이
 * - 사운드: WebAudio 합성 띵동 (외부 파일·인터넷 불필요)
 */
"use strict";

const params = new URLSearchParams(location.search);
const STATION = (params.get("station") || "A").toUpperCase();
const IDLE_LIMIT_MS = 90 * 1000; // 어트랙트 자동 복귀 (대기 화면 제외)

let calledSeconds = 12;
let introImages = [];
let introIdx = 0;
let waitIntroIdx = 0;
let myNumber = null;
let code = "";
let idleTimer = null;

const $ = (id) => document.getElementById(id);
const screens = ["attract", "intro", "code", "dosan", "printing", "wait", "called"];
let current = "attract";

function show(name) {
  current = name;
  for (const s of screens) $("screen-" + s).classList.toggle("hidden", s !== name);
  resetIdle();
}

/* ── 유휴 복귀: 진행 중 화면에서 조작이 없으면 어트랙트로 (대기·호출 화면은 예외) ── */
function resetIdle() {
  clearTimeout(idleTimer);
  if (current === "wait" || current === "called" || current === "attract") return;
  idleTimer = setTimeout(() => show("attract"), IDLE_LIMIT_MS);
}
document.addEventListener("click", resetIdle);

/* ── 사운드: 띵동 (WebAudio 합성) ── */
let audioCtx = null;
function ensureAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === "suspended") audioCtx.resume();
}
function tone(freq, t0, dur, gain = 0.5) {
  const o = audioCtx.createOscillator();
  const g = audioCtx.createGain();
  o.type = "sine"; o.frequency.value = freq;
  g.gain.setValueAtTime(gain, t0);
  g.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
  o.connect(g).connect(audioCtx.destination);
  o.start(t0); o.stop(t0 + dur);
}
function dingDong(times = 3) {
  ensureAudio();
  const now = audioCtx.currentTime;
  for (let i = 0; i < times; i++) {
    tone(880, now + i * 1.1, 0.9);        // 띵
    tone(659, now + i * 1.1 + 0.35, 1.0); // 동
  }
}
function clickBeep() { ensureAudio(); tone(1200, audioCtx.currentTime, 0.08, 0.15); }

/* ── ① 어트랙트 ── */
$("btn-start").addEventListener("click", () => { ensureAudio(); startIntro(); });

/* ── ② 뭉클 알아보기 ── */
function startIntro() {
  introIdx = 0;
  renderIntro();
  show("intro");
}
function renderIntro() {
  const img = $("intro-img"), empty = $("intro-empty");
  if (introImages.length === 0) {
    img.classList.add("hidden"); empty.classList.remove("hidden");
    $("intro-dots").textContent = "";
    return;
  }
  img.classList.remove("hidden"); empty.classList.add("hidden");
  img.src = introImages[introIdx];
  $("intro-dots").textContent = introImages.map((_, i) => (i === introIdx ? "●" : "○")).join(" ");
}
$("btn-intro-prev").addEventListener("click", () => {
  if (!introImages.length) return;
  introIdx = (introIdx - 1 + introImages.length) % introImages.length; renderIntro();
});
$("btn-intro-next").addEventListener("click", () => {
  if (!introImages.length) return;
  introIdx = (introIdx + 1) % introImages.length; renderIntro();
});
$("btn-to-code").addEventListener("click", startCode);

/* ── ③ 코드 입력 ── */
function startCode() {
  code = "";
  renderCode();
  setCodeMsg("스마트폰으로 몬스터에 접촉해 퀴즈를 풀면 코드를 받아요 📱", "");
  show("code");
}
function renderCode() {
  const digits = document.querySelectorAll("#code-display .digit");
  digits.forEach((d, i) => (d.textContent = code[i] || ""));
}
function setCodeMsg(text, cls) {
  const el = $("code-msg");
  el.textContent = text;
  el.className = "code-msg" + (cls ? " " + cls : "");
}
function buildKeypad() {
  const pad = $("keypad");
  const keys = ["1","2","3","4","5","6","7","8","9","","0","del"];
  for (const k of keys) {
    if (k === "") { pad.appendChild(document.createElement("span")); continue; }
    const b = document.createElement("button");
    if (k === "del") { b.textContent = "지우기"; b.className = "key-del"; }
    else b.textContent = k;
    b.addEventListener("click", () => { clickBeep(); pressKey(k); });
    pad.appendChild(b);
  }
}
async function pressKey(k) {
  if (k === "del") { code = code.slice(0, -1); renderCode(); return; }
  if (code.length >= 3) return;
  code += k;
  renderCode();
  if (code.length === 3) await verifyCode();
}
async function verifyCode() {
  try {
    const r = await fetch("/api/code/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const j = await r.json();
    if (j.ok) {
      setCodeMsg(`정답! ${j.monster} 몬스터를 만났군요 🎉`, "ok");
      setTimeout(() => startDosan(j.monster), 900);
    } else {
      setCodeMsg("코드가 맞지 않아요 — 다시 확인해 주세요", "bad");
      const disp = $("code-display");
      disp.classList.add("error");
      setTimeout(() => { disp.classList.remove("error"); code = ""; renderCode(); }, 700);
    }
  } catch (e) {
    setCodeMsg("서버 연결을 확인해 주세요", "bad");
    code = ""; renderCode();
  }
}
$("btn-code-back").addEventListener("click", startIntro);

/* ── ④ 도안 선택 ── */
async function startDosan(monster) {
  const grid = $("dosan-grid");
  grid.innerHTML = "";
  $("dosan-greet").textContent = monster
    ? `${monster}의 선물! 마음에 드는 도안을 고르세요`
    : "마음에 드는 도안을 고르세요";
  let list = [];
  try {
    const r = await fetch("/api/dosan");
    list = (await r.json()).dosan;
  } catch (e) { /* 아래 빈 목록 처리 */ }
  if (!list.length) {
    grid.innerHTML = '<p style="font-size:30px;color:#999">도안 준비 중이에요 — 스태프를 불러 주세요</p>';
    show("dosan");
    return;
  }
  // 도안이 1개면 자동 사용 (설계명세서 3.4)
  if (list.length === 1) { complete(list[0].file); return; }
  for (const d of list) {
    const b = document.createElement("button");
    b.textContent = "🎨 " + d.label;
    b.addEventListener("click", () => { clickBeep(); complete(d.file); });
    grid.appendChild(b);
  }
  show("dosan");
}

/* ── ⑤ 완료 → 인쇄 → 대기 등록 ── */
async function complete(dosanFile) {
  show("printing");
  try {
    const r = await fetch("/api/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ station: STATION, dosan: dosanFile }),
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      alert(j.detail || "등록에 실패했어요 — 스태프를 불러 주세요");
      show("attract");
      return;
    }
    const j = await r.json();
    myNumber = j.number;
    startWait();
  } catch (e) {
    alert("서버 연결을 확인해 주세요");
    show("attract");
  }
}

/* ── ⑥ 대기 (미니게임 · 소개) ── */
async function startWait() {
  $("wait-number").textContent = `No. ${String(myNumber).padStart(3, "0")}`;
  selectTab("game");
  exitGame();
  await loadGameMenu();
  waitIntroIdx = 0;
  renderWaitIntro();
  show("wait");
}
function selectTab(which) {
  $("tab-game").classList.toggle("active", which === "game");
  $("tab-intro").classList.toggle("active", which === "intro");
  const inGame = !$("wait-game-frame-wrap").classList.contains("hidden");
  $("wait-game-menu").classList.toggle("hidden", which !== "game" || inGame);
  $("wait-game-frame-wrap").classList.toggle("hidden", which !== "game" || !inGame);
  $("wait-intro").classList.toggle("hidden", which !== "intro");
}
$("tab-game").addEventListener("click", () => selectTab("game"));
$("tab-intro").addEventListener("click", () => selectTab("intro"));

async function loadGameMenu() {
  const menu = $("wait-game-menu");
  menu.innerHTML = "";
  let games = [];
  try {
    const r = await fetch("/api/minigames");
    games = (await r.json()).minigames;
  } catch (e) { /* 빈 메뉴 */ }
  if (!games.length) {
    menu.innerHTML = '<p style="font-size:26px;color:#999">미니게임 준비 중!</p>';
    return;
  }
  for (const g of games) {
    const b = document.createElement("button");
    b.innerHTML = `<span class="g-emoji">${g.emoji}</span><span>${g.title}</span>` +
      (g.desc ? `<span class="g-desc">${g.desc}</span>` : "");
    b.addEventListener("click", () => { clickBeep(); openGame(g.url); });
    menu.appendChild(b);
  }
}
function openGame(url) {
  $("game-frame").src = url;
  $("wait-game-menu").classList.add("hidden");
  $("wait-game-frame-wrap").classList.remove("hidden");
}
function exitGame() {
  $("game-frame").src = "about:blank";
  $("wait-game-frame-wrap").classList.add("hidden");
  $("wait-game-menu").classList.remove("hidden");
}
$("btn-game-exit").addEventListener("click", () => { exitGame(); selectTab("game"); });

function renderWaitIntro() {
  if (!introImages.length) return;
  $("wait-intro-img").src = introImages[waitIntroIdx];
}
$("btn-wintro-prev").addEventListener("click", () => {
  if (!introImages.length) return;
  waitIntroIdx = (waitIntroIdx - 1 + introImages.length) % introImages.length; renderWaitIntro();
});
$("btn-wintro-next").addEventListener("click", () => {
  if (!introImages.length) return;
  waitIntroIdx = (waitIntroIdx + 1) % introImages.length; renderWaitIntro();
});

/* ── ⑦ 띵동 호출 — 최우선 인터럽트 ── */
function onCalled(number) {
  exitGame(); // 게임 상태는 버린다 (호출이 항상 우선)
  $("called-number").textContent = `No. ${String(number).padStart(3, "0")}`;
  show("called");
  dingDong(3);
  setTimeout(() => { myNumber = null; show("attract"); }, calledSeconds * 1000);
}

/* ── WebSocket (자동 재접속) ── */
function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === "called" && msg.station === STATION) onCalled(msg.number);
  };
  ws.onclose = () => setTimeout(connectWS, 2000); // 무고장 우선: 끊기면 재접속
  ws.onerror = () => ws.close();
  // keepalive
  setInterval(() => { if (ws.readyState === 1) ws.send("ping"); }, 25000);
}

/* ── 초기화 ── */
async function init() {
  buildKeypad();
  connectWS();
  try {
    const conf = await (await fetch("/api/config")).json();
    calledSeconds = conf.called_seconds || 12;
  } catch (e) { /* 기본값 유지 */ }
  try {
    introImages = (await (await fetch("/api/intro")).json()).intro;
  } catch (e) { introImages = []; }
  show("attract");
}
init();
