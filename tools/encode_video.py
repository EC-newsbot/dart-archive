"""홍보영상 → 웹용 mp4 + 포스터. (ffmpeg 필요)

    python tools/encode_video.py 원본.mp4 [--code 2612] [--poster-at 0.5]

출력: docs/v/{code}/promo.mp4, docs/v/{code}/poster.jpg
- 이미 웹에 적합하면(H.264+AAC, 긴 변 1280px 이하, 8Mbps 이하) 다시 인코딩하지 않고 구조만 정리한다(faststart).
  재인코딩은 화질만 깎는다.
- 그 밖이면 H.264 High / AAC 128k, 긴 변 1280px, CRF 23으로 변환한다.
- 원본은 저장소에 올리지 않는다. 같은 파일을 반복 커밋하면 저장소가 계속 커지므로, 영상이 바뀔 때만 다시 올린다.
"""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_SIDE, MAX_BITRATE = 1280, 8_000_000


def probe(src):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(src)], text=True)
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    return v, a, d["format"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--code", default="2612")
    ap.add_argument("--poster-at", default="0.5", help="포스터로 쓸 시각(초)")
    ap.add_argument("--out")
    args = ap.parse_args()

    out = Path(args.out) if args.out else ROOT / "docs" / "v" / args.code
    out.mkdir(parents=True, exist_ok=True)
    mp4, poster = out / "promo.mp4", out / "poster.jpg"

    v, a, fmt = probe(args.src)
    w, h = int(v["width"]), int(v["height"])
    bitrate = int(fmt.get("bit_rate", 0))
    ok = (v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p" and (a is None or a["codec_name"] == "aac")
          and max(w, h) <= MAX_SIDE and bitrate <= MAX_BITRATE)

    if ok:
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", args.src, "-map_metadata", "-1", "-c", "copy", "-movflags", "+faststart", str(mp4)])
        print(f"remux(재인코딩 없음) {w}x{h}")
    else:
        scale = f"scale='if(gt(iw,ih),min({MAX_SIDE},iw),-2)':'if(gt(iw,ih),-2,min({MAX_SIDE},ih))'"
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", args.src, "-map_metadata", "-1", "-vf", scale, "-c:v", "libx264",
                               "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "medium",
                               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(mp4)])
        print("재인코딩")

    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-ss", str(args.poster_at), "-i", str(mp4), "-frames:v", "1", "-q:v", "3", str(poster)])
    v2, a2, fmt2 = probe(mp4)
    print(f"{mp4.name}: {v2['width']}x{v2['height']}, {float(fmt2['duration']):.1f}초, {mp4.stat().st_size / 1024 / 1024:.2f} MB / "
          f"{poster.name}: {poster.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
