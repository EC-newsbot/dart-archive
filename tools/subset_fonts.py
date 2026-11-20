"""사이트에서 실제로 쓰는 글자만 남겨 웹폰트(woff2)로 만든다.

    python build.py && python tools/subset_fonts.py

docs/ 아래 모든 HTML의 글자를 모아 서브셋을 만든다. 원고나 템플릿 글이 바뀌면 build 후 다시 실행.
원본 폰트는 SIL OFL 1.1 (Noto CJK) — 웹 임베딩·재배포 허용. name 테이블(저작권·라이선스 문구)은 유지한다.
필요: pip install fonttools brotli
원본 폰트 위치: 아래 SOURCES 경로(Linux: fonts-noto-cjk 패키지) 또는 저장소 루트의 fonts/ 폴더.
"""
import argparse
import html
import re
from html.parser import HTMLParser
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTCollection, TTFont

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_DIRS = [ROOT / "fonts", Path("/usr/share/fonts/opentype/noto"), Path("/usr/share/fonts/truetype/noto")]

# 출력 이름 → (원본 파일, 이 글꼴의 KR 파일 계열명 키워드)
FONTS = {
    "serif-400": "NotoSerifCJK-Regular.ttc",
    "serif-500": "NotoSerifCJK-Medium.ttc",
    "sans-300": "NotoSansCJK-Light.ttc",
    "sans-400": "NotoSansCJK-Regular.ttc",
}


def find(name):
    for d in SYSTEM_DIRS:
        if (d / name).exists():
            return d / name
    raise SystemExit(f"폰트 없음: {name}  (fonts/ 폴더에 넣거나 fonts-noto-cjk 설치)")


def load_kr(path):
    """TTC 안에서 한국어(KR) 얼굴을 고른다."""
    if path.suffix.lower() == ".ttc":
        for f in TTCollection(str(path)).fonts:
            names = " ".join(str(n) for n in f["name"].names)
            if " KR" in names or "-KR" in names:
                return f
        raise SystemExit(f"KR 얼굴 없음: {path}")
    return TTFont(str(path))


# 굵기별로 어떤 요소의 글자를 담을지 (style.css의 font-family/weight 배치와 맞춰 둔다).
# 빠진 글자는 fallback 폰트로 보이므로 치명적이지는 않지만, CSS를 바꾸면 여기도 같이 본다.
#   serif-400: 본문 전부 / serif-500: 약력·정보 라벨 / sans-300: 영문명 / sans-400: 촬영지·소속·출처·하단·내비
SCOPES = {
    "serif-400": None,
    "serif-500": {"classes": {"label"}, "tags": set()},
    "sans-300": {"classes": {"en"}, "tags": set()},
    "sans-400": {"classes": {"place", "aff", "nav", "foot"}, "tags": {"cite"}},
}
VOID = {"meta", "link", "img", "br", "hr", "input"}
BASE = set(chr(c) for c in range(0x20, 0x7F)) | set("·—…‘’“”「」『』〔〕→←•")


class Collector(HTMLParser):
    """scope 안(클래스·태그가 맞는 요소와 그 자손)의 글자만 모은다. scope=None이면 본문 전체."""

    def __init__(self, scope):
        super().__init__(convert_charrefs=True)
        self.scope, self.stack, self.chars = scope, [], set()

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        cls = set((dict(attrs).get("class") or "").split())
        hit = bool(self.scope) and (bool(cls & self.scope["classes"]) or tag in self.scope["tags"])
        self.stack.append((tag, hit, tag in ("script", "style")))

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        if any(skip for _, _, skip in self.stack):
            return
        if self.scope is None or any(hit for _, hit, _ in self.stack):
            self.chars |= {c for c in data if not c.isspace()}


def collect_chars(docs, scope):
    chars = set(BASE)
    for page in Path(docs).rglob("*.html"):
        c = Collector(scope)
        c.feed(page.read_text(encoding="utf-8"))
        chars |= c.chars
    return chars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(ROOT / "docs"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = Path(args.out) if args.out else Path(args.docs) / "static" / "fonts"
    out.mkdir(parents=True, exist_ok=True)

    opts = subset.Options()
    opts.flavor = "woff2"
    opts.hinting = False            # 화면용 — 힌트 제거로 용량 절감
    opts.name_IDs = ["*"]           # 저작권·라이선스 문구 유지
    opts.notdef_outline = True
    opts.layout_features = ["kern", "ccmp", "locl", "liga", "palt", "pnum"]

    total = 0
    for out_name, src in FONTS.items():
        chars = collect_chars(args.docs, SCOPES[out_name])
        font = load_kr(find(src))
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(chars)))
        sub.subset(font)
        dest = out / f"{out_name}.woff2"
        font.flavor = "woff2"
        font.save(str(dest))
        size = dest.stat().st_size
        total += size
        print(f"  {dest.name:16} {size / 1024:6.1f} KB   글자 {len(chars)}종 (한글 {sum('가' <= c <= '힣' for c in chars)})")
    print(f"  합계 {total / 1024:.1f} KB")


if __name__ == "__main__":
    main()
