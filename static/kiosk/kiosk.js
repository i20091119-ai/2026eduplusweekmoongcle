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
let codeLen = 4;      // 최대 자릿수 (키패드 빈칸 수)
let codeLens = [4];   // 유효 자릿수 목록 — 혼합 길이 코드 지원
let introImages = [];
let introIdx = 0;
let waitIntroIdx = 0;
let myNumber = null;
let code = "";
let idleTimer = null;

const $ = (id) => document.getElementById(id);
const screens = ["attract", "intro", "code", "maker", "printing", "wait", "called", "buzzer"];
let current = "attract";

function show(name) {
  current = name;
  for (const s of screens) $("screen-" + s).classList.toggle("hidden", s !== name);
  resetIdle();
}

/* ── 유휴 복귀: 진행 중 화면에서 조작이 없으면 어트랙트로 (대기·호출 화면은 예외) ── */
function resetIdle() {
  clearTimeout(idleTimer);
  if (current === "wait" || current === "called" || current === "attract" || current === "buzzer") return;
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
/* 은행 안내방송풍 차임 — 배음 3개를 겹친 종소리 음색, 긴 여운 */
function chime(freq, t0, dur = 2.6, vol = 0.55) {
  const partials = [[1, 1], [2, 0.22], [3, 0.09]];
  for (const [mult, g] of partials) {
    const o = audioCtx.createOscillator();
    const gn = audioCtx.createGain();
    o.type = "sine";
    o.frequency.value = freq * mult;
    gn.gain.setValueAtTime(0.0001, t0);
    gn.gain.linearRampToValueAtTime(vol * g, t0 + 0.025); // 빠른 어택
    gn.gain.exponentialRampToValueAtTime(0.001, t0 + dur); // 긴 여운
    o.connect(gn).connect(audioCtx.destination);
    o.start(t0); o.stop(t0 + dur);
  }
}
function dingDong(times = 2) {
  ensureAudio();
  const now = audioCtx.currentTime + 0.05;
  for (let i = 0; i < times; i++) {
    const t = now + i * 2.4;
    chime(659.25, t);        // 띵~ (E5)
    chime(523.25, t + 0.75); // 동~ (C5)
  }
}
function clickBeep() { ensureAudio(); tone(1200, audioCtx.currentTime, 0.08, 0.15); }

/* ── ① 어트랙트 ── */
// 브로슈어는 대기존에서 읽는 흐름이므로 시작 = 바로 코드 입력 (소개는 선택)
$("btn-start").addEventListener("click", () => { ensureAudio(); startCode(); });
$("btn-attract-intro").addEventListener("click", () => { ensureAudio(); startIntro(); });

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
function buildCodeDisplay() {
  const disp = $("code-display");
  disp.innerHTML = "";
  for (let i = 0; i < codeLen; i++) {
    const s = document.createElement("span");
    s.className = "digit";
    disp.appendChild(s);
  }
  $("code-title").textContent = `몬스터가 알려준 ${codeLen}자리 코드를 입력하세요`;
}
function startCode() {
  code = "";
  buildCodeDisplay();
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
  if (code.length >= codeLen) return;
  code += k;
  renderCode();
  // 유효 자릿수에 도달할 때마다 검증 — 짧은 코드가 맞으면 통과,
  // 아니면 최대 자릿수까지 계속 입력 받는다 (혼합 길이 대응)
  if (codeLens.includes(code.length)) await verifyCode(code.length === codeLen);
}
async function verifyCode(isFinal) {
  try {
    const r = await fetch("/api/code/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, station: STATION }),
    });
    const j = await r.json();
    if (j.ok) {
      setCodeMsg("정답입니다! 🎉", "ok");
      setTimeout(() => startMaker(), 900);
    } else if (isFinal) {
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

/* ── ④ 도안 만들기 — 프로그램 3종 (성격검사 · 이상형 월드컵 · 감정 이모티콘) ── */
let makerConf = {};

function makerBody(...nodes) {
  const body = $("maker-body");
  body.innerHTML = "";
  for (const n of nodes) body.appendChild(n);
  return body;
}
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}
function bigChoice(emoji, label, sub, onclick) {
  const b = document.createElement("button");
  b.innerHTML = (emoji ? `<span class="c-emoji">${emoji}</span>` : "") +
    `<span>${label}</span>` + (sub ? `<span class="m-desc">${sub}</span>` : "");
  b.addEventListener("click", () => { clickBeep(); onclick(); });
  return b;
}

async function startMaker() {
  try {
    makerConf = (await (await fetch("/api/maker")).json()).maker || {};
  } catch (e) { makerConf = {}; }
  $("maker-title").textContent = "나만의 도안 만들기 — 방법을 고르세요";
  const menu = el("div", "maker-menu");
  const programs = [
    ["personality", () => runPersonality(makerConf.personality)],
    ["worldcup",    () => runWorldcup(makerConf.worldcup)],
    ["balance",     () => runBalance(makerConf.balance)],
    ["emotion",     () => runEmotion(makerConf.emotion)],
  ];
  let any = false;
  for (const [key, run] of programs) {
    const conf = makerConf[key];
    if (!conf) continue;
    any = true;
    const b = document.createElement("button");
    b.innerHTML = `<span class="m-emoji">${conf.emoji || "🎨"}</span>` +
      `<span>${conf.title}</span><span class="m-desc">${conf.desc || ""}</span>`;
    b.addEventListener("click", () => { clickBeep(); run(); });
    menu.appendChild(b);
  }
  if (!any) { startDosanGrid(); return; } // 설정 없으면 목록 선택으로 폴백
  makerBody(menu);
  show("maker");
}

/* 프로그램 1 — 성격검사 (16문항 유형검사: axes / 구버전 점수합산: questions) */
function runPersonality(conf) {
  if (conf.axes) return runTypeTest(conf);
  $("maker-title").textContent = conf.title;
  const scores = {};
  let qi = 0;
  function ask() {
    const q = conf.questions[qi];
    const prog = el("div", "maker-progress", `${qi + 1} / ${conf.questions.length}`);
    const question = el("div", "maker-q", q.q);
    const choices = el("div", "maker-choices");
    for (const a of q.a) {
      choices.appendChild(bigChoice("", a.t, "", () => {
        for (const [name, pt] of Object.entries(a.s || {}))
          scores[name] = (scores[name] || 0) + pt;
        qi++;
        if (qi < conf.questions.length) ask();
        else finish();
      }));
    }
    makerBody(prog, question, choices);
  }
  function finish() {
    let best = null;
    for (const [name, pt] of Object.entries(scores))
      if (!best || pt > scores[best]) best = name;
    const r = conf.results[best] || {};
    showMakerResult(r.emoji || "🐾", best, r.line || "", r.pdf);
  }
  ask();
  show("maker");
}

/* 유형검사: 문항당 7점 척도(-3~+3, 검사지 그대로) →
 * 군별 합계 음수면 neg 글자, 0 이상이면 pos 글자 (검사지 채점 규칙) */
const SCALE_CAPTIONS = {
  "-3": "매우<br>그렇다", "-2": "가깝다", "-1": "굳이<br>고르면",
  "0": "잘 모르<br>겠다", "1": "굳이<br>고르면", "2": "가깝다", "3": "매우<br>그렇다",
};
function runTypeTest(conf) {
  $("maker-title").textContent = conf.title;
  const flat = [];
  conf.axes.forEach((ax, ai) => ax.questions.forEach(q => flat.push({ ai, q })));
  const sums = conf.axes.map(() => 0);
  let qi = 0;
  function answer(v) {
    sums[flat[qi].ai] += v;
    qi++;
    if (qi < flat.length) ask();
    else finish();
  }
  function ask() {
    const { q } = flat[qi];
    const prog = el("div", "maker-progress", `${qi + 1} / ${flat.length} · 더 가까운 쪽에 표시하세요`);
    const stmts = el("div", "type-stmts");
    stmts.appendChild(el("div", "stmt stmt-l", q.l));
    stmts.appendChild(el("div", "stmt-vs", "VS"));
    stmts.appendChild(el("div", "stmt stmt-r", q.r));
    const scale = el("div", "type-scale");
    for (let v = -3; v <= 3; v++) {
      const wrap = el("div", "scale-item");
      const b = document.createElement("button");
      b.className = "scale-btn " + (v < 0 ? "s-left" : v > 0 ? "s-right" : "s-zero");
      b.classList.add("mag" + Math.abs(v));
      b.textContent = v > 0 ? `+${v}` : `${v}`;
      b.addEventListener("click", () => { clickBeep(); answer(v); });
      wrap.appendChild(b);
      wrap.appendChild(el("small", "", SCALE_CAPTIONS[String(v)]));
      scale.appendChild(wrap);
    }
    makerBody(prog, stmts, scale);
  }
  function finish() {
    const type = conf.axes.map((ax, i) => (sums[i] < 0 ? ax.neg : ax.pos)).join("");
    const r = conf.results[type] || {};
    showMakerResult(r.emoji || "🐾", `${type} · ${r.animal || type}`, r.line || "", r.pdf,
      { img: r.img, why: r.why });
  }
  ask();
  show("maker");
}

/* 프로그램 2 — 음식 이상형 월드컵 */
function runWorldcup(conf) {
  $("maker-title").textContent = conf.title;
  let round = [...conf.candidates].sort(() => Math.random() - .5);
  let next = [], mi = 0;
  const roundName = n => n === 2 ? "결승" : `${n}강`;
  function match() {
    const a = round[mi], b = round[mi + 1];
    const prog = el("div", "maker-progress",
      `${roundName(round.length)} · ${mi / 2 + 1} / ${round.length / 2}`);
    const question = el("div", "maker-q", "더 좋아하는 쪽을 클릭!");
    const choices = el("div", "maker-choices");
    choices.appendChild(bigChoice(a.emoji, a.name, "", () => pick(a)));
    choices.appendChild(el("span", "vs-badge", "VS"));
    choices.appendChild(bigChoice(b.emoji, b.name, "", () => pick(b)));
    makerBody(prog, question, choices);
  }
  function pick(winner) {
    next.push(winner);
    mi += 2;
    if (mi >= round.length) {
      if (next.length === 1)
        return showMakerResult(next[0].emoji, next[0].name, "나의 최애 음식 우승!", next[0].pdf);
      round = next; next = []; mi = 0;
    }
    match();
  }
  match();
  show("maker");
}

/* 프로그램 3 — 밸런스 게임 (16문항 → 성향 축 3개 → 결과 8종) */
function runBalance(conf) {
  $("maker-title").textContent = conf.title;
  const sums = conf.axes.map(() => 0);
  let qi = 0;
  function answer(v) {
    sums[conf.questions[qi].axis] += v;
    qi++;
    if (qi < conf.questions.length) ask();
    else finish();
  }
  function ask() {
    const q = conf.questions[qi];
    const prog = el("div", "maker-progress", `${qi + 1} / ${conf.questions.length}`);
    const question = el("div", "maker-q", conf.prompt || "둘 중 하나만 고를 수 있다면?");
    const choices = el("div", "maker-choices");
    choices.appendChild(bigChoice("", q.a, "", () => answer(+1)));
    choices.appendChild(el("span", "vs-badge", "VS"));
    choices.appendChild(bigChoice("", q.b, "", () => answer(-1)));
    makerBody(prog, question, choices);
  }
  function finish() {
    const type = conf.axes.map((ax, i) => (sums[i] >= 0 ? ax.p : ax.n)).join("");
    const r = conf.results[type] || {};
    showMakerResult(r.emoji || "🌙", r.name || type, r.line || "", r.pdf, { why: r.why, img: r.img });
  }
  ask();
  show("maker");
}

/* 프로그램 4 — 감정 이모티콘 (balance로 대체됨 · emotion.json을 되살리면 다시 노출) */
function runEmotion(conf) {
  $("maker-title").textContent = conf.title;
  const question = el("div", "maker-q", conf.prompt || "지금 내 기분은?");
  const choices = el("div", "maker-choices");
  for (const emo of conf.emotions)
    choices.appendChild(bigChoice(emo.emoji, emo.name, "", () =>
      showMakerResult(emo.emoji, emo.name, "오늘의 내 감정 이모티콘!", emo.pdf)));
  makerBody(question, choices);
  show("maker");
}

/* 결과 화면 → 인쇄 확정 (extra: img 도안 미리보기 · why 이유 설명)
 * 결과 이름·키워드·설명은 결과지(인쇄물)에도 함께 조판된다 */
function showMakerResult(emoji, name, line, pdf, extra = {}) {
  $("maker-title").textContent = "결과가 나왔어요!";
  const box = el("div", "maker-choices");
  box.appendChild(bigChoice("🖨", "이 도안으로 인쇄하기", "", () => {
    if (pdf) complete(pdf, { title: name, line, note: extra.why || "" });
    else startDosanGrid(); // 결과에 도안이 연결 안 된 경우 폴백
  }));
  box.appendChild(bigChoice("↩", "다른 방법으로 만들기", "", startMaker));
  const parts = [];
  if (extra.img) {
    const img = document.createElement("img");
    img.className = "maker-result-img";
    img.src = extra.img;
    img.alt = name;
    parts.push(img);
  } else {
    parts.push(el("div", "maker-result-emoji", emoji));
  }
  parts.push(el("div", "maker-result-name", name));
  if (line) parts.push(el("div", "maker-result-line", line));
  if (extra.why) parts.push(el("div", "maker-result-why", "💡 " + extra.why));
  parts.push(box);
  makerBody(...parts);
}

/* 폴백 — 전체 도안 목록에서 직접 선택 */
async function startDosanGrid() {
  $("maker-title").textContent = "마음에 드는 도안을 고르세요";
  const grid = el("div", "dosan-grid");
  let list = [];
  try { list = (await (await fetch("/api/dosan")).json()).dosan; } catch (e) {}
  if (!list.length) {
    makerBody(el("p", "", '<span style="font-size:30px;color:#999">도안 준비 중이에요 — 스태프를 불러 주세요</span>'));
    show("maker");
    return;
  }
  if (list.length === 1) { complete(list[0].file); return; }
  for (const d of list) {
    const b = document.createElement("button");
    b.textContent = "🎨 " + d.label;
    b.addEventListener("click", () => { clickBeep(); complete(d.file, { title: d.label }); });
    grid.appendChild(b);
  }
  makerBody(grid);
  show("maker");
}

/* ── ⑤ 완료 → 인쇄 → 대기 등록 ── */
async function complete(dosanFile, meta = {}) {
  show("printing");
  try {
    const r = await fetch("/api/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ station: STATION, dosan: dosanFile, ...meta }),
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      alert(j.detail || "등록에 실패했어요 — 스태프를 불러 주세요");
      show("attract");
      return;
    }
    const j = await r.json();
    myNumber = j.number;
    startWait(j.printed);
  } catch (e) {
    alert("서버 연결을 확인해 주세요");
    show("attract");
  }
}

/* ── ⑥ 대기 (미니게임 · 소개) ── */
async function startWait(printed = true) {
  $("wait-number").textContent = `No. ${String(myNumber).padStart(3, "0")}`;
  // 인쇄 실패를 숨기지 않는다 — 스태프 호출 안내 (등록은 유지, 관리 페이지에서 재처리)
  const banner = document.querySelector(".wait-text");
  banner.innerHTML = printed
    ? '🪑 자리에서 기다려 주세요 — <b>띵동!</b> 소리가 나면 도안을 들고 만들기존으로!'
    : '⚠ <b>도안 인쇄를 확인 중이에요 — 스태프를 불러 주세요!</b> (대기 등록은 완료)';
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

/* ── 🔒 부저 호출기 (스태프 전용 · 숨김) ──
 * 진입: 어트랙트 화면 왼쪽 위 구석을 3초 안에 5회 클릭 */
let secretClicks = 0, secretTimer = null, buzzerPoll = null;
$("secret-hotspot").addEventListener("click", () => {
  if (current !== "attract") return;
  secretClicks++;
  clearTimeout(secretTimer);
  secretTimer = setTimeout(() => { secretClicks = 0; }, 3000);
  if (secretClicks >= 5) { secretClicks = 0; openBuzzer(); }
});
function openBuzzer() {
  $("buzzer-result").textContent = "";
  show("buzzer");
  pollBuzzer();
  buzzerPoll = setInterval(pollBuzzer, 2000);
}
function closeBuzzer() {
  clearInterval(buzzerPoll);
  show("attract");
}
async function pollBuzzer() {
  try {
    const s = await (await fetch("/api/status")).json();
    $("buzzer-queue").textContent =
      "대기: " + (s.waiting.length ? s.waiting.map(w => `${w.station}(No.${String(w.number).padStart(3, "0")})`).join(" → ") : "없음");
  } catch (e) { $("buzzer-queue").textContent = "대기: 서버 연결 확인"; }
}
$("btn-buzzer-exit").addEventListener("click", closeBuzzer);
$("btn-buzzer").addEventListener("click", async () => {
  const btn = $("btn-buzzer");
  btn.disabled = true;
  ensureAudio();
  try {
    const j = await (await fetch("/api/call", { method: "POST" })).json();
    $("buzzer-result").textContent = j.ok
      ? `✅ ${j.station} 자리 · No.${String(j.number).padStart(3, "0")} 호출!`
      : "🪑 " + (j.reason || "대기 없음");
    if (j.ok) dingDong(1);
  } catch (e) { $("buzzer-result").textContent = "⚠ 서버 연결 확인"; }
  pollBuzzer();
  setTimeout(() => { btn.disabled = false; }, 1500); // 연타 방지
});

/* ── ⑦ 띵동 호출 — 최우선 인터럽트 ── */
function onCalled(number) {
  if (current === "buzzer") return; // 부저 화면(스태프 사용 중)은 호출 오버레이로 덮지 않음
  exitGame(); // 게임 상태는 버린다 (호출이 항상 우선)
  $("called-number").textContent = `No. ${String(number).padStart(3, "0")}`;
  show("called");
  dingDong(3);
  setTimeout(() => { myNumber = null; show("attract"); }, calledSeconds * 1000);
}

/* ── WebSocket (자동 재접속 — 타이머는 하나만 유지) ── */
let ws = null;
function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === "called" && msg.station === STATION) onCalled(msg.number);
  };
  ws.onclose = () => setTimeout(connectWS, 2000); // 무고장 우선: 끊기면 재접속
  ws.onerror = () => ws.close();
}
setInterval(() => { if (ws && ws.readyState === 1) ws.send("ping"); }, 25000); // keepalive 단일 타이머

/* ── 초기화 ── */
async function init() {
  buildKeypad();
  connectWS();
  try {
    const conf = await (await fetch("/api/config")).json();
    calledSeconds = conf.called_seconds || 12;
    codeLen = conf.code_length || 4;
    codeLens = conf.code_lengths || [codeLen];
  } catch (e) { /* 기본값 유지 */ }
  try {
    introImages = (await (await fetch("/api/intro")).json()).intro;
  } catch (e) { introImages = []; }
  show("attract");
}
init();
