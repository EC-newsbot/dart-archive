"""QR 생성 — 전시 1개 + 작가 5개 = 6개 (SVG, 오류정정 M 이상).

주소는 config.py의 BASE_URL을 따른다. 도메인이 바뀌면 BASE_URL만 고치고 다시 실행.
출력: qr/2612.svg, qr/2612-lyj.svg ...
"""
from pathlib import Path

import segno
import dataio

import config

ROOT = Path(__file__).parent
OUT = ROOT / "qr"


def targets(data):
    code = data["exhibition"]["code"]
    yield f"{code}", f"{config.BASE_URL}/a/{code}/"
    for artist in data["artists"]:
        yield f"{code}-{artist['code']}", f"{config.BASE_URL}/a/{code}/{artist['code']}/"
    if data.get("promo"):
        yield f"{code}-promo", f"{config.BASE_URL}/v/{code}/"


def main():
    import sys
    only = set(sys.argv[2:]) if len(sys.argv) > 2 and sys.argv[1] == "--only" else None   # 예: python qr.py --only 2612-promo
    data = dataio.load(ROOT / "data" / f"{config.EXHIBITION_CODE}.yaml")
    OUT.mkdir(exist_ok=True)
    for name, url in targets(data):
        if only and name not in only:
            continue
        qr = segno.make(url, error="m", micro=False)  # M(15%) 복원
        path = OUT / f"{name}.svg"
        # border=4: 인쇄 시 조용 영역(quiet zone) 확보. 줄이지 말 것.
        qr.save(path, kind="svg", scale=10, border=4, dark="#000000", light="#ffffff", xmldecl=True)
        # 파일 안에 해당 URL을 주석으로 남긴다
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("?>", f"?>\n<!-- {url} -->", 1), encoding="utf-8")
        print(f"{path.name:18} {url}  (version {qr.version})")


if __name__ == "__main__":
    main()
