---
name: video-translation-x-post
description: Turn a user-provided video into a polished Chinese-subtitled version, preserve existing English captions when present, add attribution, verify the export, and draft an accurate, attention-grabbing X post. Use for video translation and X publishing preparation, not for unrelated video edits.
---

# Video translation and X post

Deliver the requested video, editable Chinese `.srt`, a concise factual summary, and an X post when requested. Follow the user's latest instructions over any saved defaults. Never imply that cosmetic edits make a reused video original under X's rewards rules.

## Start each job

1. Run `python3 scripts/state.py init`; read the returned preferences and recent ledger entries. State lives outside this shareable skill and is optional for first-time users.
2. Identify the user's input file, output location, watermark, and requested publishing assets. Inspect duration, resolution, audio, subtitle tracks, and representative opening, middle, and ending frames. Confirm whether English captions are burned into the image, available as a subtitle track, or absent. Do not infer this from metadata alone.
3. Reuse trustworthy existing transcripts or subtitles. Otherwise transcribe with an available ASR tool; `scripts/transcribe.py` is one local option. Check names, numbers, claims, and cut-off endings against audio and frames before translating.

## Translate and edit

- Write idiomatic Chinese that preserves meaning, uncertainty, numbers, and speaker attribution. Keep cues readable and synchronized; save the editable `.srt`.
- If English captions exist, keep them readable and place Chinese below them. If they are absent, place Chinese directly on the video. Avoid a large solid black subtitle bar. Use a restrained broadcast-style font, outline, and background treatment; do not cover faces, demonstrations, charts, or logos.
- Add only the requested watermark. A short hook can improve the opening, but it must be accurate and visually unobtrusive. Mirror only after checking that no visible text, logos, charts, or captions would become reversed. Do not use mirroring, color changes, frame dropping, or MD5 changes as a claim of originality.
- Use 1.2× speed only when requested or saved as the user's preference. At a fixed output frame rate, speeding up naturally samples fewer video frames; avoid extra frame removal that causes jitter. Review speech, timing, logic, and any scene transition after speeding up.
- Render a short sample first. Inspect it, then render the full video with `scripts/render.py` or equivalent tools. Run `scripts/verify.py`, inspect opening/middle/end frames and audio, and confirm the delivered copy matches the verified file.

## Publish package and memory

- For an X post, start with the concrete surprising point, then explain what viewers learn. Attribute claims as the speaker's prediction or opinion, verify factual marketing claims, and identify the source when known. Do not publish or message anyone without user authorization.
- Deliver at the user's requested location, including the video and editable subtitles; provide the X text if requested. Record the actual input, choices, output paths, checks, and lesson learned in the local ledger. Update preferences only when the user establishes a reusable preference.
- For first-time setup, exact CLI examples, troubleshooting, and a complete user path, read [README.md](README.md). For a compact final review, use [references/quality-checklist.md](references/quality-checklist.md).
