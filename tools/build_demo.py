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
    games.append({"id": sub.name, "title": meta.get("title", sub.name),
                  "emoji": meta.get("emoji", "🎮"),
                  "desc": meta.get("desc", ""), "url": url})
    game_src[url] = (sub / "index.html").read_text(encoding="utf-8")


# 달토끼 캐릭터가 있으면 게임 HTML 안의 경로를 data URI로 인라인 (단일 파일 데모용)
_char = ROOT / "content/character/달토끼.png"
if _char.exists():
    _char_uri = "data:image/png;base64," + base64.b64encode(_char.read_bytes()).decode()
    game_src = {u: h.replace("/content/character/달토끼.png", _char_uri) for u, h in game_src.items()}


def js_dump(o):  # 문자열 내 </script> 로 바깥 스크립트가 닫히는 것 방지
    return json.dumps(o, ensure_ascii=False).replace("</", "<\\/")


prelude = f"""
/* ═══ 데모 모킹 — 실제 서버 없이 동작 (부스 코드와 동일 UI) ═══ */
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
  if (u.includes("/api/status"))   return _json({{ waiting: [{{ station: "A", number: DEMO.number }}] }});
  if (u.includes("/api/call"))     return _json({{ ok: true, station: "A", number: DEMO.number }});
  if (u.includes("/api/complete")) {{
    DEMO.number++;
    try {{ DEMO.lastDosan = JSON.parse(opts.body).dosan; }} catch (e) {{}}
    return _json({{ ok: true, number: DEMO.number, printed: true }});
  }}
  return _json({{}});
}};
function setGameFrame(url) {{
  document.getElementById("game-frame").srcdoc = DEMO.gameSrc[url] || "<p>준비 중</p>";
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
   데모에서는 같은 레이아웃(B5 · 하단 번호블록+QR)을 브라우저 인쇄로 재현. */
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

# 로고 PNG 인라인 (단일 파일 데모에는 외부 이미지가 없음)
logo_b64 = base64.b64encode((ROOT / "static/kiosk/logo.png").read_bytes()).decode()
body = body.replace('src="logo.png"', 'src="data:image/png;base64,' + logo_b64 + '"')

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
