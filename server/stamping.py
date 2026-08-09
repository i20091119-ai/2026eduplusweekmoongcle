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
from reportlab.pdfgen import canvas

from . import config

_FONT = "HYGothic-Medium"  # reportlab 내장 한글 CID 폰트
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
    c.setFont(_FONT, 22)
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


def _png_to_pdf(src: Path, meta: dict | None = None) -> bytes:
    """PNG 도안을 '결과지' 페이지로 조판 — 떡집 헤더 + 결과 제목·키워드 +
    도안 프레임 + 설명·색칠 가이드. 하단 30mm는 스탬프 영역으로 비움."""
    meta = meta or {}
    title = meta.get("title") or src.stem
    line = meta.get("line") or ""
    note = meta.get("note") or ""
    w, h = B5
    brand = HexColor(config.BRAND_COLOR)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=B5)

    # ── 헤더: 로고 + 떡집 이름 ──
    top = h - 11 * mm
    if _LOGO.exists():
        # 로고가 글자 포함 풀 락업이므로 단독 사용 (별도 상호 텍스트 없음)
        lw_, lh_ = 60 * mm, 20 * mm
        c.drawImage(str(_LOGO), w / 2 - lw_ / 2, top - lh_, lw_, lh_,
                    preserveAspectRatio=True, anchor="c", mask="auto")
        top -= lh_ + 2.5 * mm
    c.setFillColor(HexColor("#8a7666"))
    c.setFont(_FONT, 8.5)
    c.drawCentredString(w / 2, top, "나만의 클리커 도안 · 에듀플러스위크 2026")
    top -= 9 * mm

    # ── 결과 제목 + 키워드 ──
    c.setFillColor(black)
    c.setFont(_FONT, 24)
    c.drawCentredString(w / 2, top, title)
    top -= 8 * mm
    if line:
        c.setFillColor(brand)
        c.setFont(_FONT, 11)
        c.drawCentredString(w / 2, top, line)
        top -= 6 * mm

    # ── 하단 설명 상자 (스탬프 영역 위) ──
    note_top = 33 * mm
    if note:
        c.setFont(_FONT, 10)
        note_lines = _wrap(c, note, 10, w - 40 * mm)[:4]
        box_h = 7 * mm + len(note_lines) * 5 * mm + 6 * mm
        c.setFillColor(HexColor("#FBF6EC"))
        c.setStrokeColor(HexColor("#E3D5C0"))
        c.roundRect(14 * mm, note_top, w - 28 * mm, box_h, 3 * mm, stroke=1, fill=1)
        c.setFillColor(HexColor("#4a3a30"))
        y = note_top + box_h - 7 * mm
        for ln in note_lines:
            c.drawCentredString(w / 2, y, ln)
            y -= 5 * mm
        c.setFillColor(HexColor("#a08a70"))
        c.setFont(_FONT, 7.5)
        c.drawCentredString(w / 2, note_top + 2.5 * mm, COLOR_GUIDE)
        note_top += box_h + 4 * mm
    else:
        c.setFillColor(HexColor("#a08a70"))
        c.setFont(_FONT, 8)
        c.drawCentredString(w / 2, note_top, COLOR_GUIDE)
        note_top += 8 * mm

    # ── 도안 프레임 + 이미지 ──
    frame_x, frame_y = 13 * mm, note_top
    frame_w, frame_h = w - 26 * mm, (top - 5 * mm) - frame_y
    c.setStrokeColor(brand)
    c.setLineWidth(1.4)
    c.roundRect(frame_x, frame_y, frame_w, frame_h, 5 * mm, stroke=1, fill=0)
    inset = 4 * mm
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
