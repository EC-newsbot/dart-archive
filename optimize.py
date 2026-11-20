"""원본 이미지 → 웹용 3벌. EXIF 제거(촬영 위치 정보 방지).

    images/2612/{code}/01.jpg   (원본, 저장소에 올리지 않음)
 →  docs/a/2612/img/{code}/01.jpg     긴 변 1600px, 품질 85
    docs/a/2612/thumb/{code}/01.jpg   긴 변 600px
    assets/wall/{code}/01.jpg         긴 변 2048px (2라운드 가상 전시실용)

    python optimize.py            # 새로 바뀐 것만
    python optimize.py --force    # 전부 다시

data/2612.yaml이 있으면 각 이미지의 실제 비율과 `ratio`를 대조해 어긋나면 알려준다.
"""
import argparse
from pathlib import Path

import dataio
from PIL import Image, ImageCms, ImageOps

import config

ROOT = Path(__file__).parent
EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
SIZES = {"img": 1600, "thumb": 600}   # docs 아래
WALL = 2048
QUALITY = 85
RATIOS = {"3:2": 3 / 2, "2:3": 2 / 3, "1:1": 1.0, "4:3": 4 / 3, "3:4": 3 / 4, "16:9": 16 / 9, "5:4": 5 / 4, "4:5": 4 / 5}

_SRGB = ImageCms.createProfile("sRGB")


def to_srgb(im):
    """ICC 프로필이 sRGB가 아니면 변환. (Adobe RGB 원본이 웹에서 탁해지는 것 방지)"""
    icc = im.info.get("icc_profile")
    if icc:
        try:
            import io
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            im = ImageCms.profileToProfile(im, src, _SRGB, outputMode="RGB")
        except Exception:
            im = im.convert("RGB")
    return im.convert("RGB")


def save(im, long_side, dest):
    im = im.copy()
    im.thumbnail((long_side, long_side), Image.LANCZOS)   # 확대하지 않는다
    dest.parent.mkdir(parents=True, exist_ok=True)
    # exif/icc를 넘기지 않으면 저장 시 메타데이터가 모두 빠진다
    im.save(dest, "JPEG", quality=QUALITY, optimize=True, progressive=True)


def nearest_ratio(w, h):
    r = w / h
    return min(RATIOS, key=lambda k: abs(RATIOS[k] - r)), r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default=config.EXHIBITION_CODE)
    ap.add_argument("--src", help="원본 폴더 (기본 images/{code})")
    ap.add_argument("--docs", help="출력 docs 폴더 (기본 docs)")
    ap.add_argument("--wall", help="벽면 출력 폴더 (기본 assets/wall)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    src = Path(args.src) if args.src else ROOT / "images" / args.code
    docs = Path(args.docs) if args.docs else ROOT / "docs"
    wall = Path(args.wall) if args.wall else ROOT / "assets" / "wall"
    base = docs / "a" / args.code

    # yaml의 ratio 대조용
    declared = {}
    ypath = ROOT / "data" / f"{args.code}.yaml"
    if ypath.exists():
        data = dataio.load(ypath)
        for a in data.get("artists", []):
            for w in a.get("works") or []:
                declared[Path(w["file"]).with_suffix("").as_posix()] = w.get("ratio")

    files = sorted(p for p in src.rglob("*") if p.suffix.lower() in EXTS)
    if not files:
        raise SystemExit(f"원본 없음: {src}")

    done = skipped = 0
    for f in files:
        rel = f.relative_to(src).with_suffix(".jpg")           # lyj/01.jpg
        outs = [(base / "img" / rel, SIZES["img"]), (base / "thumb" / rel, SIZES["thumb"]), (wall / rel.parent.name / rel.name, WALL)]
        if not args.force and all(o.exists() and o.stat().st_mtime >= f.stat().st_mtime for o, _ in outs):
            skipped += 1
            continue
        with Image.open(f) as im:
            im = ImageOps.exif_transpose(im)                    # 회전 정보 반영 후 EXIF 제거
            im = to_srgb(im)
            w, h = im.size
            if max(w, h) < 2600:
                print(f"  ⚠ {rel}: 긴 변 {max(w, h)}px (원본 2600px 이상 권장)")
            key = rel.with_suffix("").as_posix()
            near, actual = nearest_ratio(w, h)
            if declared.get(key) and declared[key] != near:
                print(f"  ⚠ {rel}: yaml ratio {declared[key]} ↔ 실제 {near} ({actual:.3f})")
            for dest, side in outs:
                save(im, side, dest)
        done += 1
        print(f"  ✓ {rel}  {w}x{h}")

    print(f"\n처리 {done}장, 건너뜀 {skipped}장")


if __name__ == "__main__":
    main()
