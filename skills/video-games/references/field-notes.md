# Field notes

Dated lessons from real games, newest first. One entry per lesson: what
happened, the rule it produced, and where the rule now lives.

## 2026-09-26 — PixelPals first playable (same day)

- **Contracts first, then four parallel agents** (art, gameplay, audio,
  menus+demo) worked without collisions: the coordinator wrote the input
  autoload, `Art`/`Sfx` loaders that fall back to placeholder rects and
  silence, the screen router and an asset-name table in CLAUDE.md, then gave
  each agent exclusive paths and "do not commit". Gameplay was built and
  tested against placeholders while the art was still being drawn; dropping
  the PNGs in needed zero code changes.
- **Demo mode is the verification backbone**: scripted `demo:<n>` devices
  play every screen, so `make shot` captures real gameplay under xvfb
  (`--write-movie`, `--fixed-fps 30`) with nobody at the controls. Native
  320x180 frames upscaled 3x in a sheet were enough to review layout and art.
- **Frame 0 matters for static icons**: a spinning 4-frame star used as a
  counter icon reads as "I I I" when frames land edge-on; stop animations
  on icons.
- **Models flip sprites that do not read**: the monkey drawn side-on read as
  a duck; face-on fixed it. Check every rider as a solid silhouette.
- **Godot 4.7.2 was the latest stable** (the skill said 4.5+); pin the real
  latest when starting. Export templates are a 1.3 GB download; only the
  Linux ones are kept (`make setup-export`).
- Sound: our own synth produced 16 WAVs (4.3 MB) at -15 LUFS with seamless
  music loops, verified by measurement and spectrograms; taste still needs a
  human listen.

## 2026-09-26 — PixelPals kickoff

- Brief: couch co-op for Oriol plus kids aged 5 and 2, three pads, Linux PC
  on the TV, real pixel art, a character select with the kids' favourites.
- Concept chosen: a shared vehicle (a flying bathtub that scrolls on its
  own). Dad steers, the 5-year-old aims a turret in 4 directions and fires,
  the 2-year-old honks with any button. Nobody can get lost off-screen or die
  alone, which is why it beat three separate characters on screen.
- Engine research: Godot 4 has the most Claude Code precedent; no
  pixel-art generator or MCP clears 1k stars; Opus 5.5 still outputs no
  images. Hence our own grid renderer and lint
  ([pixel-art-pipeline.md](pixel-art-pipeline.md)).
- Fan characters (Sonic, Minions...) go in a gitignored private pack; the
  committed cast is original (penguin, monkey, fox, frog, robot).
