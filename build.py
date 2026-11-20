"""data/*.yaml → docs/ 정적 HTML.

    python build.py                      # data/*.yaml 전부 → docs/
    python build.py --data X.yaml --out /tmp/site   # 테스트용

멱등: 같은 입력이면 항상 같은 출력. 이미지는 건드리지 않는다(optimize.py 담당).
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

import dataio
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

ROOT = Path(__file__).parent
DEFAULT_COPYRIGHT = "수록 사진의 저작권은 각 작가에게 있습니다. 무단 전재와 복제를 금합니다."
PAGE_LIMIT = 3 * 1024 * 1024  # 작가 페이지 총 용량 상한 (검수 기준)


def paras(text):
    """빈 줄 기준으로 문단 분리. 문단 안의 줄바꿈은 공백으로."""
    if not text:
        return []
    out = []
    for chunk in re.split(r"\n\s*\n", str(text).strip()):
        line = " ".join(s.strip() for s in chunk.splitlines() if s.strip())
        if line:
            out.append(line)
    return out


def aspect(ratio):
    m = re.fullmatch(r"\s*(\d+)\s*:\s*(\d+)\s*", str(ratio or ""))
    return f"{m.group(1)} / {m.group(2)}" if m else ""


def validate(data):
    ex = data["exhibition"]
    problems = []
    for key in ("code", "title", "title_en", "period", "venue"):
        if not ex.get(key):
            problems.append(f"exhibition.{key} 없음")
    seen_codes = set()
    for a in data["artists"]:
        c = a.get("code")
        if not c or c in seen_codes:
            problems.append(f"작가 코드 누락/중복: {c}")
        seen_codes.add(c)
        for key in ("name", "name_en", "color", "band"):
            if not a.get(key):
                problems.append(f"{c}.{key} 없음")
        nos = set()
        for w in a.get("works") or []:
            if w.get("no") in nos:
                problems.append(f"{c} 작품 번호 중복: {w.get('no')}")
            nos.add(w.get("no"))
            for key in ("no", "title", "file"):
                if w.get(key) in (None, ""):
                    problems.append(f"{c} 작품 {w.get('no')}: {key} 없음")
    return problems


def ordered_works(works):
    """대표작이 맨 위. 나머지는 번호순. id는 원래 번호 유지."""
    works = list(works or [])
    return sorted(works, key=lambda w: (not w.get("feature", False), w["no"]))


def build_one(env, data, out):
    ex = dict(data["exhibition"])
    ex.setdefault("copyright", DEFAULT_COPYRIGHT)
    ex.setdefault("intro", "")
    ex.setdefault("intro_by", "")
    code = ex["code"]
    # 선택 항목은 빈 값으로 정규화 (템플릿에서 StrictUndefined 오류 방지)
    artists = []
    for a in data["artists"]:
        a = dict(a)
        a.setdefault("affiliation", "")
        a["bio"] = a.get("bio") or []
        a["statement"] = a.get("statement") or ""
        a["cited"] = a.get("cited") or None
        a["works"] = [dict(w, caption=w.get("caption") or "", cited=w.get("cited") or None) for w in (a.get("works") or [])]
        artists.append(a)
    base = out / "a" / code
    written = []
    problems = validate(data)
    if problems:
        for p in problems:
            print("  ✗", p, file=sys.stderr)
        raise SystemExit("데이터 검증 실패")

    # 전시 메인
    cards = []
    for a in artists:
        works = ordered_works(a.get("works"))
        card = dict(a, thumb="", thumb_alt="")
        if works:
            card["thumb"] = f"thumb/{works[0]['file']}"
            card["thumb_alt"] = works[0]["title"]
        cards.append(card)
    html = env.get_template("exhibition.html").render(ex=ex, artists=cards, root="../../")
    p = base / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    written.append(p)

    # 작가
    for i, a in enumerate(artists):
        works = [
            dict(w, src=f"../img/{w['file']}", aspect=aspect(w.get("ratio")), place=(w.get("place") or "").strip())
            for w in ordered_works(a.get("works"))
        ]
        html = env.get_template("artist.html").render(
            ex=ex, a=a, works=works,
            prev=artists[i - 1] if i > 0 else None,
            next=artists[i + 1] if i < len(artists) - 1 else None,
            root="../../../",
        )
        p = base / a["code"] / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
        written.append(p)
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="*", help="YAML 파일 (기본: data/*.yaml)")
    ap.add_argument("--out", default=str(ROOT / "docs"))
    args = ap.parse_args()

    out = Path(args.out)
    files = [Path(f) for f in args.data] if args.data else sorted((ROOT / "data").glob("*.yaml"))
    if not files:
        raise SystemExit("data/*.yaml 없음")

    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
    )
    env.filters["paras"] = paras

    written, codes = [], []
    for f in files:
        data = dataio.load(f)
        print(f"[{f.name}]")
        written += build_one(env, data, out)
        codes.append(str(data["exhibition"]["code"]))

    (out / "static").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "static" / "style.css", out / "static" / "style.css")
    written.append(out / "static" / "style.css")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    # QR로만 들어오는 아카이브: 검색엔진 색인(특히 이미지 검색)을 막는다. 공개 검색을 원하면 이 줄과 base.html의 robots 메타를 지운다.
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    latest = max(codes)
    (out / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=a/{latest}/">'
        f'<a href="a/{latest}/">a/{latest}/</a>\n', encoding="utf-8")
    written.append(out / "index.html")

    # 보고
    print("\n생성 파일")
    total = 0
    for p in written:
        size = p.stat().st_size
        total += size
        print(f"  {p.relative_to(out)!s:34} {size:>8,} B")
    print(f"  합계 {total:,} B")

    # 작가 페이지 총 용량(HTML+CSS+이미지)
    print("\n작가 페이지 용량 (이미지 포함)")
    for f in files:
        data = dataio.load(f)
        code = data["exhibition"]["code"]
        for a in data["artists"]:
            page = out / "a" / code / a["code"] / "index.html"
            size = page.stat().st_size + (out / "static" / "style.css").stat().st_size
            fonts = out / "static" / "fonts"
            if fonts.exists():
                size += sum(f.stat().st_size for f in fonts.glob("*.woff2"))
            missing = 0
            for w in a.get("works") or []:
                img = out / "a" / code / "img" / w["file"]
                if img.exists():
                    size += img.stat().st_size
                else:
                    missing += 1
            flag = "  ⚠ 3MB 초과" if size > PAGE_LIMIT else ""
            note = f"  (이미지 {missing}장 없음)" if missing else ""
            print(f"  {a['code']}  {size / 1024 / 1024:5.2f} MB{flag}{note}")


if __name__ == "__main__":
    main()
