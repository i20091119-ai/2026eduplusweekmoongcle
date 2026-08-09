"""샘플 도안 PNG 생성기 — 실제 도안이 준비되기 전 테스트/리허설용.

정사각 PNG 라인아트(1400px)를 만들어 content/dosan/<분류>/에 넣는다.
인쇄 시 서버가 결과지 템플릿(헤더·프레임·설명·스탬프)으로 자동 조판하므로
도안 자체는 그림 영역만 있으면 된다. 실제 도안 PNG로 파일만 교체하면 끝.
사용:  python tools/make_sample_dosan.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "content" / "dosan"
SIZE = 1400

# 동물 도안은 실물 PNG 16종이 이미 들어가 있어 생성하지 않음
ITEMS = {
    # 월드컵 16강 확정 엔트리와 이름 일치 (worldcup.json)
    "음식": ["삼겹살", "마라탕", "불닭볶음면", "평양냉면", "김치찌개", "치즈버거",
             "반반치킨", "돼지국밥", "로제떡볶이", "소곱창", "짜파구리", "모둠회",
             "부대찌개", "탕수육", "닭갈비", "감자탕"],
}


def make(category: str, name: str):
    d = OUT / category
    d.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    lw = 14
    cx, cy, r = SIZE // 2, SIZE // 2, SIZE // 3
    # 자리표시 라인아트: 원형 얼굴
    dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline="black", width=lw)
    er = r // 7
    for dx in (-r // 3, r // 3):
        dr.ellipse([cx + dx - er, cy - r // 4 - er, cx + dx + er, cy - r // 4 + er],
                   outline="black", width=lw)
    dr.arc([cx - r // 2, cy - r // 6, cx + r // 2, cy + r // 2], 20, 160,
           fill="black", width=lw)
    im.save(d / f"{name}.png")
    print("생성:", d / f"{name}.png")


for category, names in ITEMS.items():
    for name in names:
        make(category, name)
