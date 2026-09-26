# Opus 5.5 for games: what changed and what did not

Researched 2026-09-26 (four days after release). Re-check when a new model
ships; update this file rather than appending contradictions.

## Verified (Anthropic sources)

- **Modalities unchanged: text and images in, text out.** No image, audio or
  video output. The vision doc still says Claude "cannot generate, produce,
  edit... images".
  [Model overview](https://platform.claude.com/docs/en/models/opus-5-5/overview),
  [vision](https://platform.claude.com/docs/en/build-with-claude/vision)
- **Vision is sharper**: dense charts, diagrams and screenshots read "much
  more precisely without tools"; better at spatial relations (what an arrow
  connects, what changed between two versions). For the densest inputs
  Anthropic still recommends higher resolution plus crop/zoom tools.
  [Prompting guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)
- **Vision limits that remain**: images are processed in ~28x28 px patches;
  mistakes on images under ~200 px; approximate coordinates and counts; only
  the first frame of an animated GIF is read.
- **Long runs**: sustains multi-hour autonomous work with parallel subagents
  better than Opus 5; known failure mode: an unattended run sometimes stops
  early after a progress report.
- **Cheaper and faster** than Opus 5 ($4/$20 per M tokens, >30% faster
  output). [Announcement](https://www.anthropic.com/claude-opus-5-5)
- **API changes that break scripts**: thinking always on, default effort
  `medium`; forced `tool_choice` returns 400; text between tool calls arrives
  inside `thinking` blocks; computer use needs `computer_toolset_20260801`.
  [What's new](https://platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5)

## Community showcases (not Anthropic claims)

Pixel-art scenes, animations and small games made with Opus 5.5 are all
**code that draws** (Python pixel by pixel, canvas, Three.js) and code that
synthesizes audio (MIDI, synths). Authors call results much better than
before but "not perfect", and the showcases are curated. Examples:
[Sprite Fusion diorama](https://www.spritefusion.com/blog/opus-5-5-for-pixel-art-scenes),
[NewFace Design](https://newfacedesign.com/blog/claude-opus-5-5-art-animation-from-code),
[Phaser game agent](https://phaser.io/news/2026/09/opus-5-5-grok-4-7-and-muse-spark-1-3-in-the-phaser-game-agent).

**Unverified**: that Opus 5.5 gained a pixel-art ability as such. Nobody
measured palette adherence or pixel exactness. The visible improvement is
better code, better self-critique on rendered frames and longer runs.

## Consequences for our pipeline

- Keep art deterministic: text grids or generators -> our renderer -> lint.
  The model never guarantees exact pixels or palette compliance.
- Show the model art **upscaled** (8-16x nearest, grid overlay, palette
  legend, contact sheets under ~2000 px) and give it crop/zoom when judging
  captured frames. A raw 16x16 sprite is smaller than one vision patch.
- Use its vision for judgment (silhouette readability, player
  distinctness, frame-to-frame consistency, before/after diffs); leave counts
  and coordinates to scripts.
- Longer autonomous asset runs are reasonable: give it a checklist file and
  expect to re-prompt if it stops early.
- Audio stays scripted.
