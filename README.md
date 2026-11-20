# dart-archive

D-art 작품 아카이브 — 전시 도록의 QR로 열리는 정적 웹 아카이브.
전시 「발걸음을 멈춘 자리」(2026. 12. 17 — 12. 20, 갤러리 유원). 작업지시서 v2 기준.

배포 주소: https://ec-newsbot.github.io/dart-archive/a/2612/

## 구조

```
data/2612.yaml     전시 1건의 모든 내용 (HTML 표현을 담지 않는다)
images/2612/       작가 원본 — 저장소에 올리지 않음(.gitignore)
templates/         exhibition.html, artist.html, base.html
static/style.css   디자인 명세 6장
build.py           data → docs/ 정적 HTML
optimize.py        원본 → 1600px / 썸네일 600px / 벽면 2048px, EXIF 제거
qr.py              QR 6개 (SVG, 오류정정 M) → qr/
config.py          BASE_URL, 전시 코드
docs/              빌드 결과 (GitHub Pages가 서빙)
```

## 사용

```bash
pip install -r requirements.txt
python optimize.py     # images/2612/{작가코드}/01.jpg … → docs/ 용 이미지
python build.py        # docs/ 생성, 파일 목록과 작가 페이지별 용량 출력
python qr.py           # qr/*.svg 6개
```

테스트: `python build.py --data tests/sample.yaml --out /tmp/site`

## 메모

- 도메인을 구매하면 `config.py`의 `BASE_URL`만 바꾸고 `qr.py`를 다시 실행한다.
- YAML 로더는 `no`/`yes`를 불리언으로 읽지 않는다 (`no: 1` 작품 번호 키 때문). `dataio.py` 참고.
- 모든 링크는 상대경로다. 저장소 이름이 주소에 들어가는 프로젝트 페이지에서도 동작한다.
