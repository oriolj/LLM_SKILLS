# Field notes

Dated lessons from real games, newest first. One entry per lesson: what
happened, the rule it produced, and where the rule now lives.

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
