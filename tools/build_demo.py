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
    n: json.loads((ROOT / f"content/maker/{n}.json").read_text(encoding="utf-8"))
    for n in ("personality", "worldcup", "emotion")
}
intro = [
    "data:image/svg+xml;utf8," + quote(p.read_text(encoding="utf-8"))
    for p in sorted((ROOT / "content/intro").glob("*.svg"))
]
dosan = [
    {"file": str(p.relative_to(ROOT / "content/dosan")), "label": p.stem,
     "category": p.parent.name}
    for p in sorted((ROOT / "content/dosan").rglob("*.pdf"))
]
games, game_src = [], {}
for sub in sorted((ROOT / "content/minigame").iterdir()):
    if not (sub / "game.json").exists():
        continue
    meta = json.loads((sub / "game.json").read_text(encoding="utf-8"))
    url = f"/content/minigame/{sub.name}/index.html"
    games.append({"id": sub.name, "title": meta["title"], "emoji": meta["emoji"],
                  "desc": meta.get("desc", ""), "url": url})
    game_src[url] = (sub / "index.html").read_text(encoding="utf-8")


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
  if (u.includes("/api/config"))    return _json({{ stations: ["A","B"], called_seconds: 8, brand_color: "#7E212F", code_length: {max(len(c) for c in codes)} }});
  if (u.includes("/api/intro"))     return _json({{ intro: DEMO.intro }});
  if (u.includes("/api/maker"))     return _json({{ maker: DEMO.maker }});
  if (u.includes("/api/dosan"))     return _json({{ dosan: DEMO.dosan }});
  if (u.includes("/api/minigames")) return _json({{ minigames: DEMO.games }});
  if (u.includes("/api/code/verify")) {{
    return _json({{ ok: DEMO.codes.includes(JSON.parse(opts.body).code) }});
  }}
  if (u.includes("/api/complete")) {{ DEMO.number++; return _json({{ ok: true, number: DEMO.number, printed: true }}); }}
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
  <button id="demo-call">🔔 부저 누르기 (호출 시뮬레이션)</button>`;
document.body.appendChild(bar);
document.getElementById("demo-call").addEventListener("click", () => {
  ensureAudio();
  onCalled(myNumber || DEMO.number);
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

# 로고 SVG 인라인 (단일 파일 데모에는 외부 이미지가 없음)
logo_svg = (ROOT / "static/kiosk/logo.svg").read_text(encoding="utf-8")
body = body.replace('src="logo.svg"', 'src="data:image/svg+xml;utf8,' + quote(logo_svg) + '"')

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
