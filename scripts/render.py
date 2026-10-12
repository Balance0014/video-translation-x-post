#!/usr/bin/env python3
"""Render an attributed Chinese subtitle video from a source and translated SRT.

This renderer does not transcribe or translate. Inspect a short sample before
rendering the whole file; no automatic layout can detect every important visual.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from media_tools import find_ffmpeg


FONT_CANDIDATES = (
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
)


def fail(message: str) -> None:
    raise SystemExit(message)


def media_info(ffmpeg: str, source: Path) -> tuple[int, int, float, bool]:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(source)],
        capture_output=True, text=True, check=False, timeout=20,
    )
    output = result.stderr + result.stdout
    video_lines = [line for line in output.splitlines() if "Video:" in line]
    if not video_lines:
        fail("No video stream found in input.")
    line = video_lines[0]
    dimensions = re.search(r"\b(\d{2,5})x(\d{2,5})\b", line)
    rate = re.search(r"\b(\d+(?:\.\d+)?) fps\b", line)
    if not dimensions or not rate:
        fail(f"Could not read video size or frame rate: {line.strip()}")
    return int(dimensions[1]), int(dimensions[2]), float(rate[1]), "Audio:" in output


def locate_font(given: str | None) -> Path:
    if given:
        path = Path(given).expanduser()
        if path.is_file():
            return path
        fail(f"Font file not found: {path}")
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    fail("No CJK font found. Pass --font-file /path/to/a/Chinese/font.ttf")


def one_line_srt(source: Path, destination: Path) -> None:
    """Use one Chinese line so it stays in the small area below English."""
    blocks = []
    for block in re.split(r"\n\s*\n", source.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        if len(lines) < 3 or "-->" not in lines[1]:
            fail(f"Invalid SRT cue: {block[:80]!r}")
        blocks.append("\n".join((lines[0], lines[1], "".join(s.strip() for s in lines[2:]))))
    if not blocks:
        fail("Subtitle file is empty.")
    destination.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def retime_srt(source: Path, destination: Path, speed: float,
               sample_seconds: float | None) -> int:
    """Export editable subtitle cues on the finished video's timeline."""
    def parse_time(value: str) -> int:
        match = re.fullmatch(r"(\d+):(\d{2}):(\d{2}),(\d{3})", value)
        if not match:
            fail(f"Invalid SRT timestamp: {value}")
        hours, minutes, seconds, millis = map(int, match.groups())
        return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis

    def write_time(milliseconds: int) -> str:
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, millis = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

    limit = round(sample_seconds * 1000) if sample_seconds is not None else None
    result = []
    for block in re.split(r"\n\s*\n", source.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        if len(lines) < 3 or " --> " not in lines[1]:
            fail(f"Invalid SRT cue: {block[:80]!r}")
        start_text, end_text = lines[1].split(" --> ", 1)
        start = round(parse_time(start_text) / speed)
        end = round(parse_time(end_text) / speed)
        if limit is not None:
            if start >= limit:
                break
            end = min(end, limit)
        if end <= start:
            continue
        result.append(f"{len(result)+1}\n{write_time(start)} --> {write_time(end)}\n"
                      + "\n".join(lines[2:]))
    if not result:
        if sample_seconds is not None:
            destination.write_text("", encoding="utf-8")
            return 0
        fail("No subtitle cues remain after retiming.")
    destination.write_text("\n\n".join(result) + "\n", encoding="utf-8")
    return len(result)


def filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: Path,
             start: int, max_width: int) -> ImageFont.FreeTypeFont:
    for size in range(start, 11, -1):
        font = ImageFont.truetype(str(font_path), size)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            return font
    fail("Title or watermark is too long for the video frame.")


def overlay_images(folder: Path, width: int, height: int, source_height: int,
                   font_path: Path, watermark: str, title: str | None,
                   watermark_position: str = "top-right",
                   title_position: str = "upper-left") -> tuple[Path | None, Path | None]:
    wm_path = None
    title_path = None
    if watermark:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        margin = round(width * 0.025)
        font = fit_font(draw, watermark, font_path, max(18, round(width * 0.019)), round(width * 0.46))
        box = draw.textbbox((0, 0), watermark, font=font, stroke_width=2)
        wm_x = margin if watermark_position == "top-left" else width - margin - (box[2] - box[0])
        draw.text((wm_x, margin), watermark,
                  font=font, fill="white", stroke_width=2, stroke_fill=(0, 0, 0, 220))
        wm_path = folder / "watermark.png"
        image.save(wm_path)
    if title:
        lines = [line.strip() for line in title.split("|") if line.strip()]
        if not 1 <= len(lines) <= 2:
            fail("--title accepts one or two lines separated by |")
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        x = round(width * 0.02)
        y = round(source_height * (0.30 if title_position == "middle-left" else 0.18))
        panel_w = round(width * (0.34 if title_position == "middle-left" else 0.39))
        panel_h = round(source_height * (0.11 if len(lines) == 1 else 0.19))
        draw.rounded_rectangle((x, y, x + panel_w, y + panel_h),
                               radius=max(8, round(width * 0.014)),
                               fill=(0, 0, 0, 190), outline=(255, 255, 255, 70), width=2)
        for index, line in enumerate(lines):
            font = fit_font(draw, line, font_path,
                            max(20, round(width * (0.030 if index == 0 else 0.031))),
                            panel_w - round(width * 0.035))
            text_y = y + round(panel_h * (0.12 if index == 0 else 0.52))
            draw.text((x + round(width * 0.018), text_y), line, font=font,
                      fill=(255, 204, 70, 255) if index == 0 else "white")
        title_path = folder / "title.png"
        image.save(title_path)
    return wm_path, title_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--subtitles", required=True, type=Path, help="Checked Chinese SRT")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--output-subtitles", type=Path,
                        help="Editable SRT for the final timeline; defaults beside output video")
    parser.add_argument("--layout", required=True, choices=("bilingual", "chinese-only"),
                        help="bilingual assumes English is already visible in the source")
    parser.add_argument("--english-subtitles", type=Path,
                        help="English SRT to render when English is a separate track/file")
    parser.add_argument("--watermark", default="")
    parser.add_argument("--watermark-position", choices=("top-left", "top-right"),
                        default="top-right")
    parser.add_argument("--title", help="One or two short lines, separated by |")
    parser.add_argument("--title-position", choices=("upper-left", "middle-left"),
                        default="upper-left")
    parser.add_argument("--title-seconds", type=float, default=3.0)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--mirror", action="store_true")
    parser.add_argument("--mirror-verified", action="store_true",
                        help="Confirms visible writing/logos will not become reversed")
    parser.add_argument("--font-file")
    parser.add_argument("--font-name", default="PingFang SC", help="Font family for FFmpeg subtitles")
    parser.add_argument("--sample-seconds", type=float, help="Make a short preview first")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    source = args.input.expanduser().resolve()
    subtitles = args.subtitles.expanduser().resolve()
    output = args.output.expanduser().resolve()
    output_subtitles = (args.output_subtitles or output.with_suffix(".srt")).expanduser().resolve()
    if not source.is_file() or not subtitles.is_file():
        fail("Input video or Chinese SRT does not exist.")
    if output == source:
        fail("Output must be different from input.")
    if output_subtitles == subtitles or output_subtitles == output:
        fail("Exported SRT must not replace the source SRT or video.")
    if output.exists() and not args.overwrite:
        fail(f"Output already exists: {output} (pass --overwrite to replace it)")
    if output_subtitles.exists() and not args.overwrite:
        fail(f"Exported SRT already exists: {output_subtitles} (pass --overwrite to replace it)")
    if args.layout != "bilingual" and args.english_subtitles:
        fail("--english-subtitles requires --layout bilingual")
    if args.english_subtitles and not args.english_subtitles.is_file():
        fail("English SRT does not exist.")
    if args.mirror and (args.layout == "bilingual" or not args.mirror_verified):
        fail("Mirror requires chinese-only layout and --mirror-verified after visual inspection.")
    if not 0.5 <= args.speed <= 2.0 or args.title_seconds <= 0:
        fail("Speed must be 0.5–2.0 and title duration must be positive.")
    if args.sample_seconds is not None and args.sample_seconds <= 0:
        fail("Sample duration must be positive.")
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        fail("ffmpeg not found. Install FFmpeg with libass and put it on PATH.")
    width, source_height, fps, has_audio = media_info(ffmpeg, source)
    if not has_audio:
        fail("Input has no audio stream; check that the correct source was selected.")
    font_path = locate_font(args.font_file)
    output_height = source_height
    if args.layout == "bilingual":
        extra = max(60, round(source_height * 0.111))
        output_height += extra + (extra % 2)
    output.parent.mkdir(parents=True, exist_ok=True)
    output_subtitles.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="video-translation-x-") as temp_name:
        temp = Path(temp_name)
        chinese = temp / "zh.srt"
        if args.layout == "bilingual":
            one_line_srt(subtitles, chinese)
        else:
            shutil.copyfile(subtitles, chinese)
        wm, title = overlay_images(temp, width, output_height, source_height,
                                   font_path, args.watermark, args.title,
                                   args.watermark_position, args.title_position)
        inputs = ["-i", str(source)]
        overlays = []
        for image in (wm, title):
            if image:
                inputs.extend(["-loop", "1", "-i", str(image)])
                overlays.append(image)

        chain = []
        base = "[0:v]"
        if args.mirror:
            chain.append(f"{base}hflip[flipped]")
            base = "[flipped]"
        if args.english_subtitles:
            en = temp / "en.srt"
            shutil.copyfile(args.english_subtitles, en)
            en_style = (f"FontName={args.font_name},FontSize=19,Outline=2,Shadow=0,"
                        "Alignment=2,MarginV=22")
            chain.append(f"{base}subtitles='{filter_path(en)}':force_style='{en_style}'[english]")
            base = "[english]"
        if args.layout == "bilingual":
            chain.append(f"{base}setsar=1,split=2[foreground][backdrop]")
            # Sample the middle of the picture for the subtitle extension.
            # The source's own lower third can be black or carry name labels.
            chain.append(f"[backdrop]crop=iw:ih*0.5:0:ih*0.25,"
                         f"scale={width}:{output_height},gblur=sigma=18,"
                         "eq=brightness=-0.16,setsar=1[soft]")
            chain.append("[soft][foreground]overlay=0:0:shortest=1[canvas]")
            base = "[canvas]"
            size, margin = 21, 8
        else:
            size, margin = 23, 24
        zh_style = (f"FontName={args.font_name},FontSize={size},"
                    "PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,"
                    f"BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV={margin}")
        chain.append(f"{base}subtitles='{filter_path(chinese)}':force_style='{zh_style}'[chinese]")
        base = "[chinese]"
        image_index = 1
        if wm:
            chain.append(f"{base}[{image_index}:v]overlay=0:0:shortest=1[watermarked]")
            base = "[watermarked]"
            image_index += 1
        if title:
            chain.append(f"{base}[{image_index}:v]overlay=0:0:"
                         f"enable='between(t,0,{args.title_seconds})':shortest=1[titled]")
            base = "[titled]"
        chain.append(f"{base}setpts=PTS/{args.speed},fps={fps:.6f},setsar=1[v]")
        chain.append(f"[0:a]atempo={args.speed}[a]")
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", *inputs,
               "-filter_complex", ";".join(chain), "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
               "-movflags", "+faststart"]
        if args.sample_seconds is not None:
            cmd.extend(["-t", str(args.sample_seconds)])
        cmd.extend(["-y" if args.overwrite else "-n", str(output)])
        print(f"Rendering {output} ({width}x{output_height}, {fps:g} fps, {args.speed:g}x)")
        try:
            subprocess.run(cmd, check=True, timeout=7200)
        except subprocess.CalledProcessError as error:
            fail(f"FFmpeg render failed (exit {error.returncode}).")
        except subprocess.TimeoutExpired:
            fail("FFmpeg render exceeded the 2-hour limit.")
        count = retime_srt(chinese, output_subtitles, args.speed, args.sample_seconds)
    print(output)
    print(f"Editable subtitles: {output_subtitles} ({count} cues)")


if __name__ == "__main__":
    main()
