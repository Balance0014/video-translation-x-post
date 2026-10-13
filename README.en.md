# X Video Localization & Posting

[中文说明](README.md) · [Real task case study](examples/马斯克访谈案例.md) · [Play the original layout demo](examples/layout-demo.mp4) · [Synced SRT example](examples/layout-demo.srt)

![Original layout demo: English in the source frame and Chinese beneath it](examples/layout-demo.png)

The demo graphics, line of dialogue, and synthesized voice were made for this repository. It shows layout, attribution, and 1.2× speed; the text case study describes a real translation job.

Every X-ready localized export must add a brief, accurate on-screen hook in the first 2–3 seconds. Do not skip it because the source already explains its topic in speech. Inspect the sample and final file to confirm the hook is present and does not cover the speaker, existing captions, logos, or attribution.

An independent Codex skill for giving user-provided English videos a distinctive Chinese localized edition with a stronger original feel: checked, natural translation; clean bilingual layout; an accurate opening hook; considered pacing and attribution; a verified export; synced SRT; and an editable X post draft. This describes the presentation of the localized edition, not eligibility for X's Original Content Rewards. Codex checks and translates the content; the scripts help with transcription drafts, rendering, verification, and records. The skill is MIT licensed. Your preferences and job ledger stay outside this folder, so sharing the skill does not share your private history.

Hidden audio or visual perturbations are not a routine deduplication step. Adversarial effects are model-specific, may be removed by upload transcoding, and do not establish originality. Preserve clear audio and picture, accurate translation, and source attribution.

## 0. Install and check prerequisites

Clone the public repository into your skills directory, or copy/download the whole folder there:

```bash
git clone https://github.com/Balance0014/video-translation-x-post.git ~/.codex/skills/video-translation-x-post
```

If you set `$CODEX_HOME`, use `$CODEX_HOME/skills/video-translation-x-post/` instead. Restart/reload Codex so `$video-translation-x-post` is discoverable. On macOS/Linux, install FFmpeg with the `subtitles`/libass filter and Python 3.10+; on Windows, WSL is the recommended shell path.

```bash
python3 --version
cd ~/.codex/skills/video-translation-x-post
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/self_test.py
```

If FFmpeg or a Chinese font is missing, install them with your OS package manager, then rerun the self-test. The scripts look for `ffmpeg` on `PATH`, in `~/.local/bin`, and in Homebrew's common Apple Silicon location. The self-test makes a tiny synthetic clip and checks both layouts; it does not download a speech model or publish anything. `faster-whisper` is only needed when the input has no dependable transcript; its model downloads on first use unless you pass a local model directory.

## 1. Give Codex the real job

Attach a video or give its absolute path, then use a request such as:

> Use `$video-translation-x-post` on `/absolute/path/input.mp4`. Make natural Chinese subtitles. Keep existing English captions if present and put Chinese below; if absent, use Chinese alone. Add `翻译：@yourhandle`, a short accurate opening hook, and a ready-to-post X summary. Use 1.2× only if speech and scene logic stay clear. Save the video and SRT to my Desktop. Do not post it for me.

The agent should inspect the opening, middle, and ending frames before choosing a layout, read your local preferences, then show a short render sample before full export. You can override any saved preference in the request.

## 2. Transcript and translation path

Use an existing reliable transcript or subtitle track first. A separate English subtitle track can be extracted with FFmpeg; inspect the stream index before using this example:

```bash
mkdir -p work
ffmpeg -i input.mp4 -map 0:s:0 work/english.srt
```

For English speech with no reliable text, generate a **draft** with the included local ASR helper:

```bash
python scripts/transcribe.py --input input.mp4 --output work/english-draft.srt --language en --model base.en
```

Have Codex check the draft against audio and frames, then translate it into `work/chinese.srt`. The ASR output is not a finished translation. Ask the agent to verify names, numbers, claims, timing, and cut-off endings. The final Chinese should sound native while preserving the speaker's meaning and uncertainty. The renderer exports a second, retimed SRT next to the finished video, so it stays synchronized after 1.2× speed.

For long videos, process time-coded batches and save the transcript, translation, and corrections in `work/`. Correct individual cues without retranscribing or retranslating the whole source, and do not resend the entire transcript through the model on every revision. Before the full render, read the complete Chinese SRT for fluency; check uncertain lines against audio and source text, including names, numbers, speaker changes, and shot or slide transitions. Check for empty, invalid, or overlapping cues and coverage of the opening and ending. Visual spot checks do not replace a complete text review.

## 3. Render a sample, then the full video

Choose `bilingual` when English is already burned into the video or supply `--english-subtitles work/english.srt` when English exists only as a separate SRT. Choose `chinese-only` when there is no English. For `bilingual`, the renderer extends the picture softly below the original frame so Chinese can sit under English without a solid black bar. It joins Chinese cue lines into one line for this compact area; inspect long cues in the sample and shorten them if necessary.

```bash
python scripts/render.py --input input.mp4 --subtitles work/chinese.srt \
  --output work/sample.mp4 --layout bilingual --watermark '翻译：@yourhandle' \
  --title '关键人物说了什么|准确的开场钩子' --speed 1.2 --sample-seconds 8
```

Watch the sample. Check English and Chinese order, readability, faces, charts, the watermark, title placement, speech clarity, and motion. If an existing logo occupies the top right, pass `--watermark-position top-left`. Even without English dialogue captions, the soft extension can protect source name labels or other important lower-third content. Revise the SRT or layout before the full export. Render the final with the same options and a new output path, without `--sample-seconds`:

Settle the subtitles, hook, layout, font size, and speed before starting a long full render. Fix and rerender if final QA reveals a real defect; the pre-render gate removes avoidable rework without weakening quality checks.

If the default upper-left title would overlap a speaker, use `--title-position middle-left` or `--title-position lower-left`. When the picture is crowded, bilingual layout supports `--title-position band-left` for a one-line hook in the upper part of the soft subtitle extension. Confirm the placement in the sample. For square high-resolution clips, use `--subtitle-font-size 12` or another checked value if Chinese text is clipped horizontally.

```bash
python scripts/render.py --input input.mp4 --subtitles work/chinese.srt \
  --output work/final.mp4 --layout bilingual --watermark '翻译：@yourhandle' \
  --title '关键人物说了什么|准确的开场钩子' --speed 1.2
python scripts/verify.py --output work/final.mp4 --source input.mp4 --speed 1.2
```

For a video with no English, replace `--layout bilingual` with `--layout chinese-only`; the Chinese goes on the original frame. Use `--mirror --mirror-verified` only after visual inspection confirms that no readable text or logo becomes reversed. The renderer refuses mirroring in bilingual mode. Speeding up at the original output frame rate naturally samples fewer frames; extra frame deletion is unnecessary.

## 4. Deliver, write X copy, and remember the result

Copy the verified video and editable Chinese SRT to the requested folder. Check that the copied video matches the verified export:

```bash
cp work/final.mp4 ~/Desktop/final.mp4
cp work/final.srt ~/Desktop/final.srt
python scripts/verify.py --output work/final.mp4 --source input.mp4 --speed 1.2 \
  --delivered ~/Desktop/final.mp4
```

Have Codex write an X post with a concrete hook, the actual takeaways, and source attribution when known. Label predictions as predictions. A changed MD5, filter, mirror, or text overlay does not by itself make someone else's footage original under [X's current rewards rules](https://help.x.com/en/using-x/original-content-rewards). Do not publish without the account owner's instruction.

Run `python scripts/state.py init` once; it prints the private preference and ledger paths. Edit preferences for lasting choices. After every job, append a dated Markdown ledger entry with real input/output paths, decisions, checks, and lessons:

```bash
python scripts/state.py record --entry-file work/ledger-entry.md
```

If a process or temporary file was started for the job, end or remove it after the deliverable is verified. Keep reusable ASR caches only when they make future jobs faster.

## Troubleshooting

- **No English text but `bilingual` chosen:** use `chinese-only`.
- **Chinese overlaps English or runs off screen:** shorten the cue, inspect the sample, or adjust layout rather than adding a thick black bar.
- **Font is missing:** pass `--font-file /path/to/CJK-font.ttf` and, if needed, `--font-name 'Installed Font Family'`.
- **Speech sounds rushed at 1.2×:** lower `--speed`; the user's latest request controls the choice.
- **Mirrored writing appears backward:** remove `--mirror`; preserving readable writing takes priority.
- **Export metadata shows non-square pixels:** rerender with the script and run `verify.py` again.
