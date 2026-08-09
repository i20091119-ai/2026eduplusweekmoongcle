"""키오스크 데모 빌더 — 서버 API를 모킹해 단일 HTML(docs/demo/index.html)로 조립.

GitHub Pages 등 정적 호스팅에서 부스 키오스크 UI를 그대로 체험할 수 있다
(콘텐츠 · 미니게임 전부 내장, 인쇄·대기열은 시뮬레이션).
사용:  python tools/build_demo.py
"""
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo" / "index.html"

html = (ROOT / "static/kiosk/index.html").read_text(encoding="utf-8")
css = (ROOT / "static/kiosk/kiosk.css").read_text(encoding="utf-8")
js = (ROOT / "static/kiosk/kiosk.js").read_text(encoding="utf-8")

# 브랜드 서체 — 파일 안에 폰트가 1벌만 실리도록 CSS에는 마커를 두고
# 실제 data URI는 JS 상수(FONT_URI)로 한 번만 넣어 런타임에 치환한다.
import base64 as _b64f
font_uri = {}
for _w in ("light", "medium", "bold"):
    _fp = ROOT / f"static/kiosk/fonts/esamanru-{_w}.woff2"
    if _fp.exists():
        font_uri[_w] = "data:font/woff2;base64," + _b64f.b64encode(_fp.read_bytes()).decode()
        css = css.replace(f'url("fonts/esamanru-{_w}.woff2")', f'url("__FONT_{_w}__")')

# ── 콘텐츠 수집 ──
codes = json.loads((ROOT / "content/quiz/quiz.json").read_text(encoding="utf-8"))["codes"]
maker = {
    f.stem: json.loads(f.read_text(encoding="utf-8"))
    for f in sorted((ROOT / "content/maker").glob("*.json"))
}
import base64
import io
import mimetypes

def _intro_data_uri(p: Path) -> str:
    if p.suffix.lower() == ".svg":
        return "data:image/svg+xml;utf8," + quote(p.read_text(encoding="utf-8"))
    try:  # 단일 파일 데모가 비대해지지 않게 축소·JPEG 변환 (키오스크는 원본 사용)
        from PIL import Image
        im = Image.open(p).convert("RGB")
        im.thumbnail((1280, 1280))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()

intro = [
    _intro_data_uri(p)
    for p in sorted((ROOT / "content/intro").iterdir())
    if p.suffix.lower() in {".svg", ".png", ".jpg", ".jpeg", ".webp"}
]
dosan = [
    {"file": str(p.relative_to(ROOT / "content/dosan")), "label": p.stem,
     "category": p.parent.name}
    for p in sorted((ROOT / "content/dosan").rglob("*"))
    if p.is_file() and p.suffix.lower() in {".pdf", ".png"}
]

# 성격검사 결과 이미지(/content/dosan/...)를 단일 파일 데모용 data URI로 인라인
def _thumb_data_uri(p: Path, size=420, q=80) -> str:
    import base64 as _b64
    from PIL import Image
    im = Image.open(p).convert("RGB")
    im.thumbnail((size, size))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q)
    return "data:image/jpeg;base64," + _b64.b64encode(b.getvalue()).decode()

import io
for r in maker.get("personality", {}).get("results", {}).values():
    img = r.get("img", "")
    if img.startswith("/content/dosan/"):
        f = ROOT / "content" / "dosan" / img.removeprefix("/content/dosan/")
        if f.exists():
            r["img"] = _thumb_data_uri(f)
# 월드컵 우승 화면의 도안 미리보기도 인라인 (kiosk는 w.img 우선 사용)
for c in maker.get("worldcup", {}).get("candidates", []):
    f = ROOT / "content" / "dosan" / c.get("pdf", "")
    if c.get("pdf") and f.exists():
        c["img"] = _thumb_data_uri(f)


# content/ui 슬롯 이미지 인라인 — maker JSON 안 경로 + kiosk.js 안 경로 모두
def _inline_ui(o):
    if isinstance(o, dict):
        return {k: _inline_ui(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_inline_ui(v) for v in o]
    if isinstance(o, str) and o.startswith("/content/ui/"):
        f = ROOT / "content" / "ui" / o.removeprefix("/content/ui/")
        if f.exists():
            return _alpha_thumb_uri(f, 420)
    return o
def _alpha_thumb_uri(p, size=480):
    """투명 배경 유지 축소 인라인 (WebP) — 데모 파일 크기 억제."""
    import io as _io
    from PIL import Image
    im = Image.open(p)
    im.thumbnail((size, size))
    b = _io.BytesIO()
    im.save(b, "WEBP", quality=85)
    return "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode()


games, game_src = [], {}
for sub in sorted((ROOT / "content/minigame").iterdir()):
    # 서버(list_minigames)와 동일한 관용 규칙: game.json + index.html 둘 다 있어야 게임
    if not (sub.is_dir() and (sub / "game.json").exists() and (sub / "index.html").exists()):
        continue
    try:
        meta = json.loads((sub / "game.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    url = f"/content/minigame/{sub.name}/index.html"
    g = {"id": sub.name, "title": meta.get("title", sub.name),
         "emoji": meta.get("emoji", "🎮"),
         "desc": meta.get("desc", ""), "url": url}
    html_src = (sub / "index.html").read_text(encoding="utf-8")
    # 게임 내부 이미지 슬롯(assets/*) 인라인 — 게임들이 `assets/떡${i}.png`처럼
    # 경로를 런타임에 조립하므로 문자열 치환 대신 Image.src 인터셉터로 매핑한다.
    assets_dir = sub / "assets"
    if assets_dir.is_dir():
        amap = {}
        for a in sorted(assets_dir.iterdir()):
            if a.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                # 배경류는 화면 전체에 깔리므로 고해상도 유지
                amap[a.name] = _alpha_thumb_uri(a, 1920 if a.stem.startswith("배경") else 360)
        if amap:
            shim = ("<script>window.__ASSETS__=" + json.dumps(amap, ensure_ascii=False)
                    + ";(function(){var d=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,'src');"
                    + "Object.defineProperty(HTMLImageElement.prototype,'src',{"
                    + "set:function(v){var m=String(v).match(/(?:^|\\/)assets\\/([^\\/]+)$/);"
                    + "d.set.call(this,(m&&window.__ASSETS__[decodeURIComponent(m[1])])||v);},"
                    + "get:function(){return d.get.call(this);}});})();</script>")
            html_src = html_src.replace("<body>", "<body>" + shim, 1)
    if (sub / "icon.png").exists():
        g["icon"] = _alpha_thumb_uri(sub / "icon.png", 280)
    games.append(g)
    game_src[url] = html_src


# 달토끼 캐릭터가 있으면 게임 HTML 안의 경로를 data URI로 인라인 (단일 파일 데모용)
_char = ROOT / "content/character/달토끼.png"
if _char.exists():
    _char_uri = _alpha_thumb_uri(_char)
    game_src = {u: h.replace("/content/character/달토끼.png", _char_uri) for u, h in game_src.items()}

# 게임 HTML의 서체 참조(/kiosk/fonts/…)를 마커로 — 실제 폰트는 FONT_URI 1벌만 싣는다
game_src = {
    u: re.sub(r"/kiosk/fonts/esamanru-(light|medium|bold)\.woff2", r"__FONT_\1__", h)
    for u, h in game_src.items()
}


maker = _inline_ui(maker)
# kiosk.js의 applyUiSlots가 참조하는 /content/ui/ 경로도 실제 파일이 있으면 인라인
for _p in (ROOT / "content/ui").rglob("*.png"):
    _rel = "/content/ui/" + _p.relative_to(ROOT / "content/ui").as_posix()
    if _rel in js:
        js = js.replace(_rel, _alpha_thumb_uri(_p, 420))


def js_dump(o):  # 문자열 내 </script> 로 바깥 스크립트가 닫히는 것 방지
    return json.dumps(o, ensure_ascii=False).replace("</", "<\\/")


prelude = f"""
/* ═══ 데모 모킹 — 실제 서버 없이 동작 (부스 코드와 동일 UI) ═══ */
/* 브랜드 서체 data URI — 파일 안에 1벌만 싣고 CSS·게임의 __FONT_*__ 마커를 런타임 치환 */
const QR_URI = {js_dump(_alpha_thumb_uri(ROOT / "static/kiosk/qr.png", 300) if (ROOT / "static/kiosk/qr.png").exists() else "")};
const FONT_URI = {js_dump(font_uri)};
function applyFontUris(s) {{
  return s.replace(/__FONT_(light|medium|bold)__/g, (m, w) => FONT_URI[w] || "");
}}
document.querySelectorAll("style").forEach(st => {{
  if (st.textContent.includes("__FONT_")) st.textContent = applyFontUris(st.textContent);
}});
const DEMO = {{
  codes: {js_dump(codes)},
  maker: {js_dump(maker)},
  intro: {js_dump(intro)},
  dosan: {js_dump(dosan)},
  games: {js_dump(games)},
  gameSrc: {js_dump(game_src)},
  number: 6,
}};
window.WebSocket = class {{ constructor() {{ this.readyState = 0; }} send() {{}} close() {{}} }};
const _json = (data) => Promise.resolve({{ ok: true, status: 200, json: async () => data }});
window.fetch = (url, opts) => {{
  const u = String(url);
  if (u.includes("/api/config"))    return _json({{ stations: ["A","B"], called_seconds: 8, brand_color: "#7E212F", code_length: {max(len(c) for c in codes)}, code_lengths: {sorted({len(c) for c in codes})} }});
  if (u.includes("/api/intro"))     return _json({{ intro: DEMO.intro }});
  if (u.includes("/api/maker"))     return _json({{ maker: DEMO.maker }});
  if (u.includes("/api/dosan"))     return _json({{ dosan: DEMO.dosan }});
  if (u.includes("/api/minigames")) return _json({{ minigames: DEMO.games }});
  if (u.includes("/api/code/verify")) {{
    return _json({{ ok: DEMO.codes.includes(JSON.parse(opts.body).code) }});
  }}
  if (u.includes("/api/admin/reprint")) return _json({{ ok: true }});
  if (u.includes("/api/status"))   return _json({{ waiting: [{{ station: "A", number: DEMO.number }}],
    recent: [{{ number: DEMO.number, station: "A", dosan: "동물/여우.png", status: "waiting" }}] }});
  if (u.includes("/api/call"))     return _json({{ ok: true, station: "A", number: DEMO.number }});
  if (u.includes("/api/complete")) {{
    DEMO.number++;
    try {{
      const b = JSON.parse(opts.body);
      DEMO.lastDosan = b.dosan;
      // 실제 서버와 동일: title·line·note가 최상위 필드로 온다
      DEMO.lastMeta = {{ title: b.title || "", line: b.line || "", note: b.note || "" }};
    }} catch (e) {{}}
    setTimeout(demoPrint, 400); // 실제 부스처럼 도안 결과지를 프린터로
    return _json({{ ok: true, number: DEMO.number, printed: true }});
  }}
  return _json({{}});
}};
/* ── 데모 자동 인쇄: 결과지(A4 조판)를 숨은 iframe으로 만들어 프린터로 보낸다.
 * 크롬을 --kiosk-printing 옵션으로 실행하면 대화상자 없이 기본 프린터로 바로 출력. ── */
function demoDosanImg(path) {{
  if (!path) return "";
  for (const conf of Object.values(DEMO.maker)) {{
    for (const r of Object.values(conf.results || {{}}))
      if (r.pdf === path && r.img) return r.img;
    for (const c of (conf.candidates || []))
      if (c.pdf === path && c.img) return c.img;
  }}
  return "";
}}
function demoPrint() {{
  const meta = DEMO.lastMeta || {{}};
  const img = demoDosanImg(DEMO.lastDosan);
  const logo = document.querySelector(".logo-badge");
  const old = document.getElementById("print-frame");
  if (old) old.remove();
  const f = document.createElement("iframe");
  f.id = "print-frame";
  f.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden";
  document.body.appendChild(f);
  const d = f.contentDocument;
  d.open();
  d.write(applyFontUris(`<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    @font-face {{ font-family:"esamanru"; font-weight:400 600; src:url("__FONT_medium__") format("woff2"); }}
    @font-face {{ font-family:"esamanru"; font-weight:700 900; src:url("__FONT_bold__") format("woff2"); }}
    @page {{ size: 210mm 297mm; margin: 0; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; width:210mm; height:297mm; font-family:"esamanru","Pretendard","Malgun Gothic",sans-serif;
      background:#FFFDF6; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
    .page {{ position:absolute; inset:5mm 5.5mm; border:1.6pt solid #7E212F; border-radius:5mm;
      display:flex; flex-direction:column; align-items:center; text-align:center; }}
    .page::before {{ content:""; position:absolute; inset:1.4mm; border:1pt dashed #E0B84E; border-radius:4mm; }}
    .dot {{ position:absolute; width:3.6mm; height:3.6mm; background:#F2C744; border-radius:50%; }}
    .dot::after {{ content:""; position:absolute; inset:1.1mm; background:#7E212F; border-radius:50%; }}
    .logo {{ height:22mm; margin-top:7mm; }}
    .sub {{ color:#8a7666; font-size:8.5pt; margin:2.5mm 0 3mm; }}
    .sub b {{ color:#F2C744; }}
    h1 {{ font-size:23pt; margin:0 0 3mm; color:#2b2320; }}
    .line {{ display:inline-block; background:#F2C744; color:#7E212F; font-size:10.5pt; font-weight:700;
      border-radius:99px; padding:1.6mm 6mm; margin-bottom:4mm; }}
    .frame {{ position:relative; width:172mm; height:145mm; border:1.5pt solid #7E212F; border-radius:5mm;
      display:flex; align-items:center; justify-content:center; }}
    .frame::before {{ content:""; position:absolute; inset:2mm; border:1pt dashed #E0B84E; border-radius:3.6mm; }}
    .frame img {{ max-width:160mm; max-height:133mm; }}
    .notewrap {{ position:relative; width:172mm; margin-top:6mm; }}
    .chip {{ position:absolute; top:-3mm; left:50%; transform:translateX(-50%); background:#7E212F; color:#fff;
      font-size:8pt; border-radius:99px; padding:1mm 4.5mm; white-space:nowrap; }}
    .note {{ background:#FBF4E4; border:1px solid #E3CFA8; border-radius:3.5mm;
      font-size:10pt; color:#4a3a30; padding:5mm 7mm 3mm; line-height:1.65; }}
    .guide {{ font-size:7.5pt; color:#a08a70; margin-top:2mm; }}
    .band {{ margin-top:auto; margin-bottom:2mm; width:186mm; background:#F9EFD7; border-radius:3.5mm;
      display:flex; justify-content:space-between; align-items:center; padding:3mm 5mm; }}
    .num {{ background:#7E212F; color:#fff; font-size:16pt; font-weight:800; border-radius:3mm; padding:3mm 11mm; }}
    .foot {{ font-size:7pt; color:#b49b78; }}
    .qr {{ font-size:8pt; color:#555; }}
  </style></head><body><div class="page">
    <span class="dot" style="left:2mm;top:2mm"></span><span class="dot" style="right:2mm;top:2mm"></span>
    <span class="dot" style="left:2mm;bottom:2mm"></span><span class="dot" style="right:2mm;bottom:2mm"></span>
    ${{logo ? `<img class="logo" src="${{logo.src}}">` : ""}}
    <div class="sub"><b>●</b>&nbsp; 나만의 클리커 도안 · 에듀플러스위크 2026 (데모 인쇄) &nbsp;<b>●</b></div>
    <h1>${{meta.title || ""}}</h1>
    ${{meta.line ? `<div class="line">${{meta.line}}</div>` : ""}}
    <div class="frame">${{img ? `<img src="${{img}}">` : "<span style='color:#bbb'>도안 미리보기 없음</span>"}}</div>
    ${{meta.note ? `<div class="notewrap"><span class="chip">이 도안이 어울리는 이유</span>
      <div class="note">${{meta.note}}<div class="guide">색칠 순서: 밝은 면, 어두운 면, 검정 외곽선, 흰색 하이라이트 (아크릴마카 3색 이내)</div></div></div>` : ""}}
    <div class="band"><span class="num">No. ${{String(DEMO.number).padStart(3, "0")}}</span>
      <span class="foot">뭉클 떡집 · 제17회 에듀플러스위크 미래교육박람회</span>
      <span class="qr">${{QR_URI ? `<img src="${{QR_URI}}" style="height:15mm;display:block;margin:0 auto 1mm">` : ""}}뭉클 더 알아보기</span></div>
  </div></body></html>`));
  d.close();
  // 이미지·서체 로딩이 끝난 뒤 인쇄 (안 그러면 빈 칸으로 찍힘)
  setTimeout(async () => {{
    try {{
      await d.fonts.ready;
      await Promise.all([...d.images].map(im => im.decode().catch(() => {{}})));
      f.contentWindow.focus();
      f.contentWindow.print();
    }} catch (e) {{ try {{ f.contentWindow.print(); }} catch (e2) {{}} }}
  }}, 250);
}}
function setGameFrame(url) {{
  document.getElementById("game-frame").srcdoc = applyFontUris(DEMO.gameSrc[url] || "<p>준비 중</p>");
}}
function clearGameFrame() {{
  const f = document.getElementById("game-frame");
  f.removeAttribute("srcdoc"); f.src = "about:blank";
}}
"""

# 게임 iframe을 srcdoc으로 교체
js = js.replace('$("game-frame").src = url;', "setGameFrame(url);")
js = js.replace('$("game-frame").src = "about:blank";', "clearGameFrame();")

demo_ui = """
/* ═══ 데모 조작부 ═══ */
const bar = document.createElement("div");
bar.id = "demo-bar";
bar.innerHTML = `<span class="demo-chip">🎪 데모 — 코드: <b>__CODES__</b></span>
  <button id="demo-call">🔔 부저 누르기 (호출 시뮬레이션)</button>
  <button id="demo-print">🖨 도안 인쇄 미리보기</button>`;
document.body.appendChild(bar);
document.getElementById("demo-call").addEventListener("click", () => {
  ensureAudio();
  onCalled(myNumber || DEMO.number);
});
/* 데모 인쇄: 실제 부스에서는 서버가 스탬프한 PDF를 프린터로 보낸다.
   데모에서는 같은 레이아웃(A4 · 하단 번호블록+QR)을 브라우저 인쇄로 재현. */
document.getElementById("demo-print").addEventListener("click", () => {
  const label = (DEMO.lastDosan || "동물/여우.pdf").split("/").pop().replace(".pdf", "");
  const num = String(myNumber || DEMO.number).padStart(3, "0");
  const doc = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    @page { size: 182mm 257mm; margin: 0; }
    body { margin:0; width:182mm; height:257mm; font-family:sans-serif; position:relative; }
    h1 { text-align:center; margin-top:18mm; font-size:24pt; }
    .sub { text-align:center; color:#666; font-size:10pt; }
    svg.face { display:block; margin:16mm auto 0; }
    .num { position:absolute; left:12mm; bottom:7mm; width:52mm; height:16mm; background:#7E212F;
      border-radius:3mm; color:#fff; font-size:20pt; font-weight:bold; display:flex;
      align-items:center; justify-content:center; }
    .num-label { position:absolute; left:12mm; bottom:24mm; font-size:8pt; }
    .qr { position:absolute; right:12mm; bottom:6mm; width:18mm; height:18mm; border:1.2mm solid #000;
      display:flex; align-items:center; justify-content:center; font-size:7pt; text-align:center; }
    .qr-label { position:absolute; right:12mm; bottom:25mm; width:18mm; text-align:center; font-size:8pt; }
  </style></head><body>
    <h1>뭉클 클리커 도안 — ${label}</h1>
    <p class="sub">(데모 인쇄 — 실제 부스에서는 서버가 도안 PDF에 자동 스탬프)</p>
    <svg class="face" width="380" height="380" viewBox="0 0 200 200" fill="none" stroke="#000" stroke-width="2">
      <circle cx="100" cy="100" r="80"/><circle cx="72" cy="85" r="9"/><circle cx="128" cy="85" r="9"/>
      <path d="M70 125 Q100 150 130 125"/>
    </svg>
    <span class="num-label">오늘의 참여번호</span><div class="num">No. ${num}</div>
    <span class="qr-label">뭉클 더 알아보기</span><div class="qr">QR</div>
  </body></html>`;
  const f = document.createElement("iframe");
  f.style.cssText = "position:fixed;width:0;height:0;border:none";
  document.body.appendChild(f);
  f.srcdoc = doc;
  f.onload = () => { f.contentWindow.print(); setTimeout(() => f.remove(), 60000); };
});
""".replace("__CODES__", " · ".join(codes))

demo_css = """
/* 데모 조작부 — 실제 부스 화면에는 없음 */
#demo-bar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 200;
  display: flex; gap: 12px; align-items: center; justify-content: center;
  padding: 8px; background: rgba(43,43,43,.92); }
#demo-bar .demo-chip { color: #ffd97a; font-size: 15px; }
#demo-bar button { font-size: 16px; font-weight: 700; padding: 10px 20px;
  border-radius: 10px; background: #7E212F; color: #F2C744; box-shadow: none; }
.screen { bottom: 48px !important; }
#screen-called.screen { bottom: 0 !important; }
"""

body = re.search(r"<body>\n(.*)\n<script src=\"kiosk\.js\"></script>", html, re.S).group(1)

# 로고 인라인 (단일 파일 데모에는 외부 이미지가 없음) — 축소 WebP
body = body.replace('src="logo.png"', 'src="' + _alpha_thumb_uri(ROOT / "static/kiosk/logo.png", 600) + '"')
_mark = ROOT / "static/kiosk/logo-mark.png"
if _mark.exists():
    body = body.replace('src="logo-mark.png"', 'src="' + _alpha_thumb_uri(_mark, 128) + '"')

page = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>뭉클 부스 키오스크 데모</title>
<meta name="viewport" content="width=1280">
<style>
{css}
{demo_css}
</style>
</head>
<body>
{body}
<script>
{prelude}
{js}
{demo_ui}
</script>
</body>
</html>
"""
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page, encoding="utf-8")
print("built:", OUT, f"{len(page):,} bytes")
