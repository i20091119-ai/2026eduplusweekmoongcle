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


def stamp_pdf(src: Path, number: int, dst: Path) -> Path:
    """src 도안 PDF의 첫 페이지에 스탬프를 합성해 dst로 저장."""
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
