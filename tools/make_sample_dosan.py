"""샘플 도안 PDF 생성기 — 실제 도안이 준비되기 전 테스트/리허설용.

도안 만들기 프로그램 3종(성격검사·월드컵·감정)의 모든 결과에 대응하는
자리표시 도안을 content/dosan/<분류>/ 에 생성한다.
규격: B5 세로(JIS 182×257mm — 출력 확정) · 본문 흑백 라인아트 · 하단 30mm 비움.
사용:  python tools/make_sample_dosan.py
"""
from pathlib import Path

from reportlab.lib.colors import black
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

FONT = "HYGothic-Medium"
pdfmetrics.registerFont(UnicodeCIDFont(FONT))

OUT = Path(__file__).resolve().parent.parent / "content" / "dosan"
PAGE = (182 * mm, 257 * mm)  # JIS B5 세로
W, H = PAGE
BOTTOM = 30 * mm  # 하단 여백 — 시스템이 번호·QR 스탬프

ITEMS = {
    "동물": ["여우", "강아지", "부엉이", "펭귄"],
    "음식": ["피자", "치킨", "떡볶이", "초밥", "햄버거", "파스타", "김밥", "아이스크림"],
    "감정": ["기쁨", "설렘", "뿌듯", "궁금", "씩씩", "평온"],
}


def make(category: str, name: str):
    d = OUT / category
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.pdf"
    c = canvas.Canvas(str(path), pagesize=PAGE)
    c.setStrokeColor(black)

    c.setFont(FONT, 24)
    c.drawCentredString(W / 2, H - 25 * mm, f"뭉클 클리커 도안 — {name}")
    c.setFont(FONT, 11)
    c.drawCentredString(W / 2, H - 33 * mm, f"({category} · 샘플 — 실제 도안 PDF로 교체하세요)")

    # 자리표시 라인아트: 원형 얼굴 + 이름
    cx, cy, r = W / 2, H / 2 + 10 * mm, 55 * mm
    c.setLineWidth(2)
    c.circle(cx, cy, r)
    c.circle(cx - r * 0.35, cy + r * 0.25, r * 0.12)
    c.circle(cx + r * 0.35, cy + r * 0.25, r * 0.12)
    c.arc(cx - r * 0.4, cy - r * 0.5, cx + r * 0.4, cy + r * 0.1, 200, 140)
    c.setFont(FONT, 30)
    c.drawCentredString(cx, cy - r - 16 * mm, name)

    # 하단 여백 경계 안내선 (실제 도안에서는 제거)
    c.setDash(4, 6)
    c.setLineWidth(0.5)
    c.line(10 * mm, BOTTOM, W - 10 * mm, BOTTOM)
    c.setFont(FONT, 8)
    c.drawCentredString(W / 2, BOTTOM + 2 * mm, "↓ 이 아래 30mm는 시스템 스탬프 영역 (비워 둘 것)")
    c.save()
    print("생성:", path)


for category, names in ITEMS.items():
    for name in names:
        make(category, name)
