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
python tools/subset_fonts.py   # build 다음에. docs/static/fonts/ 웹폰트 생성
python qr.py           # qr/*.svg (전시 1 + 작가 5 + 홍보영상 1)
python tools/encode_video.py 원본.mp4   # 홍보영상 → docs/v/2612/ (promo.mp4, poster.jpg)
```

테스트: `python build.py --data tests/sample.yaml --out /tmp/site`

## 메모

- 홍보영상은 별도 페이지 `/v/2612/`(전시 아카이브 `/a/2612/`와 분리). 자동재생 없음, 재생 전에는 포스터(약 16KB)만 받는다. 영상이 바뀔 때만 다시 커밋한다(같은 파일을 반복 커밋하면 저장소 용량이 계속 늘어난다).

- 서체: 도록과 같은 Noto Serif/Sans CJK KR(본명조·본고딕, SIL OFL). 본문 Serif 400·500, 보조 Sans 300·400, Bold 미사용. 글자 수가 많은 한글 폰트라 `tools/subset_fonts.py`가 사이트에서 쓰는 글자만 남겨 woff2(합계 약 165KB)로 만든다. 원고나 템플릿 글이 바뀌면 build 후 다시 실행. 원본 폰트는 `fonts/`(gitignore) 또는 시스템 폰트 폴더에서 읽는다.

- 반응형: 같은 HTML이 모바일(기본, 375px 기준)과 PC(900px 이상, 최대 880px)에서 다르게 배치된다. 색·서체·행간은 공통.
- 웹용 이미지는 긴 변 1200px(품질 85), 썸네일 400px. 원본 유출 방지를 위해 일부러 작게 둔다.

- 도메인을 구매하면 `config.py`의 `BASE_URL`만 바꾸고 `qr.py`를 다시 실행한다.
- YAML 로더는 `no`/`yes`를 불리언으로 읽지 않는다 (`no: 1` 작품 번호 키 때문). `dataio.py` 참고.
- 모든 링크는 상대경로다. 저장소 이름이 주소에 들어가는 프로젝트 페이지에서도 동작한다.
