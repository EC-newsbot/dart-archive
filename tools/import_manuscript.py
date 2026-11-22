"""디자인용역_원고.docx → data/2612.yaml

    python tools/import_manuscript.py 원고.docx data/2612.yaml

원고가 수정되면 다시 돌려서 YAML을 새로 만든다. (필요: pip install python-docx)

원고 취급 규칙(원고 4장)
- 글은 고치지 않는다. 띄어쓰기·따옴표도 그대로.
- 줄바꿈은 '의미 단위' 표시일 뿐이다 → 같은 문단 안의 줄은 공백으로 잇는다.
- 문단 구분은 docx의 문단 아래 간격(space_after)으로 읽는다 (1pt = 같은 문단, 11pt = 문단 끝).
- 작품 제목·촬영지는 원고 끝 '캡션 목록' 표를 기준으로 한다.
- 〔인용문 …〕 은 디자이너에게 주는 지시문이라 데이터에 넣지 않는다.
"""
import json
import re
import sys
from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

PARA_BREAK_PT = 100000        # EMU. 이 이상이면 문단 끝 (원고: 12700 vs 139700)
STANDARD = {"3:2": 3 / 2, "2:3": 2 / 3, "1:1": 1.0, "4:3": 4 / 3, "3:4": 3 / 4, "16:9": 16 / 9, "9:16": 9 / 16, "5:4": 5 / 4, "4:5": 4 / 5}

# 작가 색 (작업지시서 6-1)
COLORS = {
    "이영준": ("lyj", "#C98A63", "#E6DCD3"),
    "임재선": ("ljs", "#9BAE86", "#DEE2D7"),
    "임현숙": ("ihs", "#7FACA9", "#D7E0DF"),
    "최순옥": ("cso", "#8A9CC0", "#D9DDE4"),
    "박인숙": ("pis", "#C9AE70", "#E7E1CF"),
}

EXHIBITION = {
    "code": "2612", "title": "발걸음을 멈춘 자리", "title_en": "WHERE WE STOPPED WALKING",
    "tagline": "다섯 사람이 멈춰 선 다섯 개의 자리", "year": 2026,
    "period": "2026. 12. 17(목) — 12. 20(일)", "hours": "10:00 — 18:00",
    "venue": "갤러리 유원", "address": "대전광역시 중구 대종로550번길 5, 유원오피스텔 403호",
    "admission": "무료", "host": "(사)한국디지털사진가협회", "producer": "D-art",
    "support": "중소벤처기업부 2026년 2차 모두의 창업 프로젝트",
    "copyright": "수록 사진의 저작권은 각 작가에게 있습니다. 무단 전재와 복제를 금합니다.",
}

# 여는 글 — 원고 docx에 없어 발주처가 별도 전달한 텍스트. 문단은 네 개(원문 줄 묶음), 서명은 따로.
INTRO = [
    "사진을 찍는 사람은 걷다가 멈춘 사람입니다. 남들이 지나치는 자리에서 걸음을 멈추고, 몸을 낮추고, 때로는 몇십 분을 그대로 서 있습니다. 그렇게 멈춰 선 자리에서 한 장이 남습니다.",
    "이 책에 실린 다섯 분은 저마다 다른 곳에서 멈추셨습니다. 어떤 분은 깊은 산 그늘에 핀 손톱만 한 꽃 앞에서, 어떤 분은 물안개가 피어오르는 호수 한가운데에서 멈추셨습니다. 멈춘 자리가 다르니 남은 사진도 다릅니다.",
    "다섯 개의 자리를 한 권에 모았습니다. 서로 닮지 않은 것이 이 책의 내용입니다.",
    "작품 곁에 적힌 글은 작가들이 직접 들려주신 이야기를 옮긴 것입니다. 사진이 찍힌 날의 날씨와 기다린 시간, 그 자리에 가게 된 까닭이 거기에 있습니다. 사진만으로는 보이지 않는 것들입니다.",
]
INTRO_BY = "D-art"

# 홍보영상 별도 아카이브 (/v/2612/). 파일은 tools/encode_video.py가 docs/v/2612/에 만든다.
PROMO = {"title": "홍보영상", "file": "promo.mp4", "poster": "poster.jpg", "width": 796, "height": 1128}


def flatten(path):
    d = docx.Document(path)
    items = []
    for ch in d.element.body.iterchildren():
        tag = ch.tag.split("}")[1]
        if tag == "p":
            p = Paragraph(ch, d)
            items.append(("p", p.text, p.paragraph_format.space_after, p.paragraph_format.left_indent))
        elif tag == "tbl":
            t = Table(ch, d)
            items.append(("t", [[c.text.strip() for c in r.cells] for r in t.rows], None, None))
    return items


def group(lines):
    """[(text, space_after)] → 문단 리스트. 문단 안의 줄은 공백으로 잇는다."""
    out, cur = [], []
    for text, sa in lines:
        text = text.strip()
        if not text:
            if cur:
                out.append(" ".join(cur)); cur = []
            continue
        cur.append(text)
        if sa is None or sa >= PARA_BREAK_PT:
            out.append(" ".join(cur)); cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def split_quote(lines):
    """인용 블록 줄들 → (문단 리스트, 출처). 마지막 줄이 출처."""
    lines = [(l[0], l[1]) for l in lines if not l[0].strip().startswith("〔")]
    source = lines[-1][0].strip()
    return group(lines[:-1]), source


def ratio_str(w, h):
    r = w / h
    k = min(STANDARD, key=lambda k: abs(STANDARD[k] / r - 1))
    if abs(STANDARD[k] / r - 1) <= 0.015:
        return k
    return f"{w}:{h}"      # 표준 비율이 아닌 크롭은 픽셀 그대로


def q(s):
    return json.dumps(s, ensure_ascii=False)


def emit_text(key, paras, indent):
    """문단 리스트를 YAML로. 한 문단이면 한 줄 문자열, 여러 문단이면 | 블록(빈 줄 구분)."""
    pad = " " * indent
    if not paras:
        return f'{pad}{key}: ""\n'
    if len(paras) == 1:
        return f"{pad}{key}: {q(paras[0])}\n"
    body = "\n\n".join(pad + "  " + p for p in paras)
    return f"{pad}{key}: |\n{body}\n"


def parse(path):
    items = flatten(path)
    ptexts = [(i, it[1].strip()) for i, it in enumerate(items) if it[0] == "p"]

    # 캡션 목록 표 (마지막 표)
    cap_table = [it for it in items if it[0] == "t"][-1][1]
    caps = []
    for row in cap_table[1:]:
        no, artist, title, place, fname, px = row
        w, h = [int(x) for x in re.findall(r"\d+", px)]
        feat = "(대표작)" in title
        caps.append(dict(g=int(no), artist=artist, title=title.replace("(대표작)", "").strip(), place=place, fname=fname,
                         w=w, h=h, feature=feat))

    starts = [i for i, t in ptexts if re.fullmatch(r"작가 \d", t)]
    end = next(i for i, t in ptexts if t == "캡션 목록")
    bounds = list(zip(starts, starts[1:] + [end]))

    artists = []
    for a, b in bounds:
        seg = items[a:b]
        pt = [(k, it) for k, it in enumerate(seg) if it[0] == "p"]
        name, name_en, aff = seg[1][1].strip(), seg[2][1].strip(), seg[3][1].strip()
        idx = {it[1].strip(): k for k, it in pt if it[1].strip() in ("약력", "작가의 말", "대표작", "수록 작품")}

        bio = [{"label": r[0], "text": r[1]} for r in next(it for it in seg[idx["약력"]:] if it[0] == "t")[1][1:]]

        # 작가의 말: 인용(들여쓰기) 블록과 본문 분리
        stmt = seg[idx["작가의 말"] + 1: idx["대표작"]]
        stmt = [(it[1], it[2], it[3]) for it in stmt if it[0] == "p"]
        quote = [(t, s) for t, s, li in stmt if li]
        body = [(t, s) for t, s, li in stmt if not li]
        cited = None
        if quote:
            qp, src = split_quote(quote)
            cited = {"text": qp, "source": src}
        statement = group(body)

        # 대표작
        rep = seg[idx["대표작"] + 1: idx["수록 작품"]]
        rep = [it for it in rep if it[0] == "p"]
        rep_title, rep_place = rep[0][1].strip(), rep[1][1].strip()
        rep_caption = group([(it[1], it[2]) for it in rep[2:]])

        # 수록 작품
        works_raw, cur = [], None
        for it in seg[idx["수록 작품"] + 1:]:
            if it[0] != "p":
                continue
            m = re.match(r"^(\d+)\.\s+(.*?)\s{2,}(.*)$", it[1].strip()) or re.match(r"^(\d+)\.\s+(.*)$", it[1].strip())
            if m and not it[3]:
                cur = {"n": int(m.group(1)), "title": m.group(2).strip(), "lines": []}
                works_raw.append(cur)
            elif cur is not None and it[1].strip():
                cur["lines"].append((it[1], it[2], it[3]))
        artists.append(dict(name=name, name_en=name_en, aff=aff, bio=bio, cited=cited, statement=statement,
                            rep=(rep_title, rep_place, rep_caption), works=works_raw))

    # 작품 조립 + 캡션 표 대조
    result = []
    for a in artists:
        code, color, band = COLORS[a["name"]]
        mine = [c for c in caps if c["artist"] == a["name"]]
        expected = 1 + len(a["works"])
        if len(mine) != expected:
            raise SystemExit(f"{a['name']}: 캡션 목록 {len(mine)}점 ↔ 본문 {expected}점")
        works = []
        for k, c in enumerate(mine, start=1):
            w = {"no": k, "title": c["title"], "place": c["place"], "file": f"{code}/{k:02d}.jpg",
                 "ratio": ratio_str(c["w"], c["h"]), "orig": c["fname"]}
            if k == 1:
                assert c["feature"] and c["title"] == a["rep"][0], f"{a['name']} 대표작 불일치"
                w["feature"] = True
                w["caption"] = a["rep"][2]
            else:
                raw = a["works"][k - 2]
                assert raw["n"] == k - 1 and raw["title"] == c["title"], f"{a['name']} {raw['n']} 제목 불일치: {raw['title']} / {c['title']}"
                lines = raw["lines"]
                if lines and lines[0][0].strip().startswith("〔인용문"):
                    qp, src = split_quote(lines)
                    w["cited"] = {"text": qp, "source": src}
                    w["caption"] = []
                else:
                    w["caption"] = group([(t, s) for t, s, li in lines])
            works.append(w)
        result.append(dict(code=code, name=a["name"], name_en=a["name_en"], aff=a["aff"], color=color, band=band,
                           bio=a["bio"], cited=a["cited"], statement=a["statement"], works=works))
    return result


def render(artists):
    o = ["# 자동 생성: python tools/import_manuscript.py 원고.docx data/2612.yaml\n"
         "# 원고가 바뀌면 직접 고치지 말고 스크립트를 다시 돌린다. (여는 글은 원고 docx에 없어 이 스크립트의 INTRO에 있다)\n",
         "exhibition:\n"]
    for k, v in EXHIBITION.items():
        o.append(f"  {k}: {q(v) if isinstance(v, str) else v}\n")
    o.append(emit_text("intro", INTRO, 2))
    o.append(f"  intro_by: {q(INTRO_BY)}\n\n")
    o.append("promo:\n")
    for k, v in PROMO.items():
        o.append(f"  {k}: {q(v) if isinstance(v, str) else v}\n")
    o.append("\n")
    o.append("artists:\n")
    for a in artists:
        o.append(f"  - code: {a['code']}\n    name: {q(a['name'])}\n    name_en: {q(a['name_en'])}\n"
                 f"    affiliation: {q(a['aff'])}\n    color: {q(a['color'])}\n    band: {q(a['band'])}\n")
        if a["bio"]:
            o.append("    bio:\n")
            for r in a["bio"]:
                o.append(f"      - {{ label: {q(r['label'])}, text: {q(r['text'])} }}\n")
        else:
            o.append("    bio: []\n")
        if a["cited"]:
            o.append("    cited:\n")
            o.append(emit_text("text", a["cited"]["text"], 6))
            o.append(f"      source: {q(a['cited']['source'])}\n")
        o.append(emit_text("statement", a["statement"], 4))
        o.append("    works:\n")
        for w in a["works"]:
            o.append(f"      - no: {w['no']}\n        title: {q(w['title'])}\n        place: {q(w['place'])}\n"
                     f"        file: {q(w['file'])}\n        ratio: {q(w['ratio'])}\n")
            if w.get("feature"):
                o.append("        feature: true\n")
            o.append(f"        orig: {q(w['orig'])}   # 원본 파일명(대조용)\n")
            if w.get("cited"):
                o.append("        cited:\n")
                o.append(emit_text("text", w["cited"]["text"], 10))
                o.append(f"          source: {q(w['cited']['source'])}\n")
            o.append(emit_text("caption", w["caption"], 8))
        o.append("\n")
    return "".join(o)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    Path(dst).write_text(render(parse(src)), encoding="utf-8")
    print("wrote", dst)
