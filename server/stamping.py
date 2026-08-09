"""도안 하단 30mm 여백 스탬프 — 좌측 참여번호(브랜드 컬러 블록), 우측 뭉클 QR.

도안 파일 규격 (B5 세로 확정 — 2026-08-09):
- B5 세로 · PDF · 본문 흑백 라인아트
- 하단 여백 30mm 비움 (필수) → 인쇄 직전 시스템이 자동 스탬프
오버레이는 원본 PDF의 실제 페이지 크기를 따라가므로 A4 도안이 섞여도 안전.
"""
import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from . import config

# 브랜드 서체(esamanru) TTF가 있으면 결과지도 같은 서체로 — 없으면 내장 CID 폰트
_FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "kiosk" / "fonts"
try:
    pdfmetrics.registerFont(TTFont("esamanru", str(_FONTS_DIR / "esamanru-medium.ttf")))
    pdfmetrics.registerFont(TTFont("esamanru-bold", str(_FONTS_DIR / "esamanru-bold.ttf")))
    _FONT, _FONT_BOLD = "esamanru", "esamanru-bold"
except Exception:
    _FONT = _FONT_BOLD = "HYGothic-Medium"  # reportlab 내장 한글 CID 폰트
    pdfmetrics.registerFont(UnicodeCIDFont(_FONT))


def _overlay(number: int, pagesize: tuple[float, float]) -> bytes:
    """하단 30mm 영역에 올릴 오버레이 PDF 생성 — 원본 페이지 크기에 맞춤."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=pagesize)
    w, _h = pagesize

    # ── 좌측: 참여번호 블록 (여기만 브랜드 컬러 — 토너 절약 + 식별성) ──
    block_w, block_h = 52 * mm, 16 * mm
    bx, by = 15 * mm, 7 * mm
    c.setFillColor(HexColor(config.BRAND_COLOR))
    c.roundRect(bx, by, block_w, block_h, 3 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont(_FONT_BOLD, 22)
    c.drawCentredString(bx + block_w / 2, by + 4.5 * mm, f"No. {number:03d}")
    c.setFillColor(black)
    c.setFont(_FONT, 8)
    c.drawString(bx, by + block_h + 2 * mm, "오늘의 참여번호")

    # ── 우측: 뭉클 QR + 캡션 ──
    qr_size = 18 * mm
    qx = w - 15 * mm - qr_size
    qy = 6 * mm
    widget = QrCodeWidget(config.QR_URL)
    b = widget.getBounds()
    d = Drawing(
        qr_size, qr_size,
        transform=[qr_size / (b[2] - b[0]), 0, 0, qr_size / (b[3] - b[1]), 0, 0],
    )
    d.add(widget)
    renderPDF.draw(d, c, qx, qy)
    c.setFont(_FONT, 8)
    c.drawCentredString(qx + qr_size / 2, qy + qr_size + 1.5 * mm, config.QR_CAPTION)

    c.save()
    return buf.getvalue()


import re as _re

# 인쇄 서체(한글 전용)에 없는 이모지·기호는 □로 찍히므로 제거
_EMOJI_RE = _re.compile(
    "[\U0001F000-\U0001FAFF\U0001FB00-\U0001FFFF☀-➿⬀-⯿️‍✨]+"
)


def _clean(s: str) -> str:
    return " ".join(_EMOJI_RE.sub("", s).split())


B5 = (182 * mm, 257 * mm)  # PNG 도안 조판용 페이지 크기 (JIS B5 세로)
_LOGO = Path(__file__).resolve().parent.parent / "static" / "kiosk" / "logo.png"
# 내장 CID 폰트가 지원하는 문자만 사용 (이모지·화살표 금지)
COLOR_GUIDE = "색칠 순서: 밝은 면, 어두운 면, 검정 외곽선, 흰색 하이라이트 (아크릴마카 3색 이내)"


def _wrap(c: canvas.Canvas, text: str, size: float, max_w: float) -> list[str]:
    """한국어 문장 단어 단위 줄바꿈."""
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if c.stringWidth(t, _FONT, size) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


MOON = "#F2C744"
CREAM_PAGE = "#FFFDF6"
BAND = "#F9EFD7"


def _png_to_pdf(src: Path, meta: dict | None = None) -> bytes:
    """PNG 도안을 '결과지' 페이지로 조판 — 크림 배경 + 이중 장식 테두리 +
    헤더·제목·키워드 필 + 도안 프레임 + 설명 상자 + 하단 스탬프 밴드."""
    meta = meta or {}
    title = _clean(meta.get("title") or src.stem)
    line = _clean(meta.get("line") or "")
    note = _clean(meta.get("note") or "")
    w, h = B5
    brand = HexColor(config.BRAND_COLOR)
    moon = HexColor(MOON)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=B5)

    # ── 페이지 배경 + 이중 장식 테두리 ──
    c.setFillColor(HexColor(CREAM_PAGE))
    c.rect(0, 0, w, h, stroke=0, fill=1)
    c.setStrokeColor(brand)
    c.setLineWidth(1.6)
    c.roundRect(5.5 * mm, 5 * mm, w - 11 * mm, h - 10 * mm, 5 * mm, stroke=1, fill=0)
    c.setStrokeColor(moon)
    c.setLineWidth(1.0)
    c.setDash(2.4, 3.2)
    c.roundRect(7.3 * mm, 6.8 * mm, w - 14.6 * mm, h - 13.6 * mm, 4 * mm, stroke=1, fill=0)
    c.setDash()
    # 네 모서리 달 점 장식
    for cx in (10.5 * mm, w - 10.5 * mm):
        for cy in (10 * mm, h - 10 * mm):
            c.setFillColor(moon)
            c.circle(cx, cy, 1.8 * mm, stroke=0, fill=1)
            c.setFillColor(brand)
            c.circle(cx, cy, 0.7 * mm, stroke=0, fill=1)

    # ── 하단 스탬프 밴드 (번호 블록·QR이 이 위에 찍힘) ──
    c.setFillColor(HexColor(BAND))
    c.roundRect(9 * mm, 6.5 * mm, w - 18 * mm, 23 * mm, 3.5 * mm, stroke=0, fill=1)
    c.setFillColor(HexColor("#b49b78"))
    c.setFont(_FONT, 7)
    c.drawCentredString(w / 2, 25.6 * mm, "뭉클 떡집 · 제17회 에듀플러스위크 미래교육박람회")

    # ── 헤더: 로고 + 부제 ──
    top = h - 13 * mm
    if _LOGO.exists():
        lw_, lh_ = 64 * mm, 21 * mm
        c.drawImage(str(_LOGO), w / 2 - lw_ / 2, top - lh_, lw_, lh_,
                    preserveAspectRatio=True, anchor="c", mask="auto")
        top -= lh_ + 3 * mm
    c.setFillColor(HexColor("#8a7666"))
    c.setFont(_FONT, 8.5)
    sub = "나만의 클리커 도안 · 에듀플러스위크 2026"
    c.drawCentredString(w / 2, top, sub)
    # 부제 양옆 작은 점 장식
    sw = c.stringWidth(sub, _FONT, 8.5)
    for dx in (-sw / 2 - 5 * mm, sw / 2 + 5 * mm):
        c.setFillColor(moon)
        c.circle(w / 2 + dx, top + 1.1 * mm, 1.1 * mm, stroke=0, fill=1)
    top -= 10 * mm

    # ── 결과 제목 + 키워드 필 ──
    c.setFillColor(HexColor("#2b2320"))
    c.setFont(_FONT_BOLD, 24)
    c.drawCentredString(w / 2, top, title)
    top -= 9.5 * mm
    if line:
        c.setFont(_FONT, 10.5)
        pw = c.stringWidth(line, _FONT, 10.5) + 12 * mm
        c.setFillColor(moon)
        c.roundRect(w / 2 - pw / 2, top - 2.6 * mm, pw, 7.6 * mm, 3.8 * mm, stroke=0, fill=1)
        c.setFillColor(brand)
        c.drawCentredString(w / 2, top - 0.2 * mm, line)
        top -= 8 * mm

    # ── 설명 상자 (라벨 칩 + 본문 + 색칠 가이드) ──
    note_top = 34 * mm
    if note:
        c.setFont(_FONT, 10)
        note_lines = _wrap(c, note, 10, w - 44 * mm)[:4]
        box_h = 8 * mm + len(note_lines) * 5 * mm + 6.5 * mm
        c.setFillColor(HexColor("#FBF4E4"))
        c.setStrokeColor(HexColor("#E3CFA8"))
        c.setLineWidth(0.9)
        c.roundRect(15 * mm, note_top, w - 30 * mm, box_h, 3.5 * mm, stroke=1, fill=1)
        # 라벨 칩 — 상자 위 테두리에 걸치게
        label = "이 도안이 어울리는 이유"
        c.setFont(_FONT, 8)
        lw2 = c.stringWidth(label, _FONT, 8) + 8 * mm
        c.setFillColor(brand)
        c.roundRect(w / 2 - lw2 / 2, note_top + box_h - 2.6 * mm, lw2, 5.6 * mm, 2.8 * mm, stroke=0, fill=1)
        c.setFillColor(white)
        c.drawCentredString(w / 2, note_top + box_h - 1 * mm, label)
        c.setFillColor(HexColor("#4a3a30"))
        c.setFont(_FONT, 10)
        y = note_top + box_h - 8.5 * mm
        for ln in note_lines:
            c.drawCentredString(w / 2, y, ln)
            y -= 5 * mm
        c.setFillColor(HexColor("#a08a70"))
        c.setFont(_FONT, 7.5)
        c.drawCentredString(w / 2, note_top + 2.6 * mm, COLOR_GUIDE)
        note_top += box_h + 6 * mm
    else:
        c.setFillColor(HexColor("#a08a70"))
        c.setFont(_FONT, 8)
        c.drawCentredString(w / 2, note_top, COLOR_GUIDE)
        note_top += 8 * mm

    # ── 도안 프레임: 버건디 외곽 + 금색 점선 내곽 + 모서리 달 점 ──
    frame_x, frame_y = 14 * mm, note_top
    frame_w, frame_h = w - 28 * mm, (top - 6 * mm) - frame_y
    c.setStrokeColor(brand)
    c.setLineWidth(1.5)
    c.roundRect(frame_x, frame_y, frame_w, frame_h, 5 * mm, stroke=1, fill=0)
    c.setStrokeColor(HexColor("#E0B84E"))
    c.setLineWidth(0.9)
    c.setDash(2.2, 2.8)
    c.roundRect(frame_x + 2 * mm, frame_y + 2 * mm, frame_w - 4 * mm, frame_h - 4 * mm,
                3.6 * mm, stroke=1, fill=0)
    c.setDash()
    for cx in (frame_x, frame_x + frame_w):
        for cy in (frame_y, frame_y + frame_h):
            c.setFillColor(moon)
            c.circle(cx, cy, 1.6 * mm, stroke=0, fill=1)
    inset = 5 * mm
    c.drawImage(
        str(src), frame_x + inset, frame_y + inset,
        frame_w - inset * 2, frame_h - inset * 2,
        preserveAspectRatio=True, anchor="c", mask="auto",
    )
    c.save()
    return buf.getvalue()


def stamp_pdf(src: Path, number: int, dst: Path, meta: dict | None = None) -> Path:
    """src 도안(PDF 또는 PNG)의 첫 페이지에 스탬프를 합성해 dst로 저장.

    PNG는 결과지 템플릿으로 조판(meta: title·line·note 반영),
    PDF는 디자이너가 만든 페이지 그대로 스탬프만 찍는다.
    """
    if src.suffix.lower() == ".png":
        reader = PdfReader(io.BytesIO(_png_to_pdf(src, meta)))
    else:
        reader = PdfReader(str(src))
    box = reader.pages[0].mediabox
    overlay_page = PdfReader(
        io.BytesIO(_overlay(number, (float(box.width), float(box.height))))
    ).pages[0]
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i == 0:
            page.merge_page(overlay_page)
        writer.add_page(page)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as f:
        writer.write(f)
    return dst
