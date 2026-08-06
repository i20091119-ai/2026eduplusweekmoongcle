"""샘플 도안 PDF 생성기 — 실제 도안이 준비되기 전 테스트/리허설용.

규격 (설계명세서 3.4): A4 세로 · 본문 흑백 라인아트 · 하단 30mm 비움.
사용:  python tools/make_sample_dosan.py
"""
from pathlib import Path

from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

FONT = "HYGothic-Medium"
pdfmetrics.registerFont(UnicodeCIDFont(FONT))

OUT = Path(__file__).resolve().parent.parent / "content" / "dosan"
OUT.mkdir(parents=True, exist_ok=True)

W, H = A4
BOTTOM = 30 * mm  # 하단 여백 — 시스템이 번호·QR 스탬프


def circle_face(c, cx, cy, r):
    c.circle(cx, cy, r)
    c.circle(cx - r * 0.35, cy + r * 0.25, r * 0.12)   # 눈
    c.circle(cx + r * 0.35, cy + r * 0.25, r * 0.12)
    c.arc(cx - r * 0.4, cy - r * 0.5, cx + r * 0.4, cy + r * 0.1, 200, 140)  # 입


def make(name: str, title: str, draw):
    path = OUT / f"{name}.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setStrokeColor(black)
    c.setLineWidth(2)
    # 제목 + 안내
    c.setFont(FONT, 24)
    c.drawCentredString(W / 2, H - 25 * mm, f"뭉클 클리커 도안 — {title}")
    c.setFont(FONT, 11)
    c.drawCentredString(W / 2, H - 33 * mm, "(샘플 — 실제 도안 PDF로 교체하세요. 하단 30mm는 비워 둡니다)")
    draw(c)
    # 하단 여백 경계 안내선 (실제 도안에서는 제거)
    c.setDash(4, 6)
    c.setLineWidth(0.5)
    c.line(10 * mm, BOTTOM, W - 10 * mm, BOTTOM)
    c.setFont(FONT, 8)
    c.drawCentredString(W / 2, BOTTOM + 2 * mm, "↓ 이 아래 30mm는 시스템 스탬프 영역 (비워 둘 것)")
    c.save()
    print("생성:", path)


def monster_round(c):
    circle_face(c, W / 2, H / 2, 60 * mm)


def monster_square(c):
    s = 100 * mm
    x, y = (W - s) / 2, (H - s) / 2 + 5 * mm
    c.roundRect(x, y, s, s, 14 * mm)
    c.circle(x + s * 0.32, y + s * 0.62, 7 * mm)
    c.circle(x + s * 0.68, y + s * 0.62, 7 * mm)
    c.arc(x + s * 0.3, y + s * 0.2, x + s * 0.7, y + s * 0.45, 200, 140)


make("동글몽", "동글몽", monster_round)
make("네모몽", "네모몽", monster_square)
