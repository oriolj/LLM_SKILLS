---
name: video-games
description: Make video games with Claude Code the way we do it — our engine choice (Godot 4 (4.7+, latest stable) with GDScript, Linux-first), real pixel art (native low-res canvas, integer scaling, a Lospec palette, indexed PNGs rendered from palette-indexed text grids by our own script and linted), couch co-op with several gamepads (roles by device id, join screen, hot-plug, SDL mappings for 8BitDo), game design for very young children (no fail states, no text, asymmetric parent+kid roles), the Claude-with-Godot traps (Godot 3 API drift, hand-edited .tscn/.uid breakage, headless renders nothing), the verification loop (GUT tests plus captured frames inspected upscaled), what Opus 5.5 can and cannot do for art and audio, third-party IP in a private pack (committed only to a private repo), and an index of the external skills and MCP servers worth reading. Use when the user says "make a game / videojoc / video game", "couch co-op", "pixel art", "sprite", "sprite sheet", "tileset", "palette", "Godot", "GDScript", "gamepad / controller support", "game for my kids", "character select", "game jam", or works in ~/git/oriolj/VideoGames/PixelPals (the couch co-op monorepo: PixelPals plus 12 planned games).
---

# Video games

How we build games with Claude Code: our preferences, what we have verified,
and where the rest of the knowledge lives. It starts from PixelPals (2026-09,
a couch co-op game for Oriol and his kids, `~/git/oriolj/VideoGames/PixelPals`)
and grows with each game; add dated lessons to
[references/field-notes.md](references/field-notes.md) as they happen.

## Preferences (Oriol)

- **All the couch co-op games live in one monorepo** (Oriol, 2026-09-26):
  `~/git/oriolj/VideoGames/PixelPals`, which is
  [oriolj/PixelPals](https://github.com/oriolj/PixelPals) (private).
  - Each game has its own `games/<slug>/` folder, and every game has a
    `PLAN.md` there before any code.
  - The input, sprite and sound autoloads live once in `shared/` and are
    symlinked into each Godot project.
  - One pinned Godot sits in the root `.tools/` and one uv venv at the root.
  - The root Makefile forwards: `make start G=<slug>`, and `make test`
    covers every game.

  Its root `CLAUDE.md` has the cross-game rules and the "start a game from
  its plan" checklist. A new kids' game goes there, not in a new repo.

- **Engine: Godot 4 (4.7+, latest stable) with GDScript.** Not C#, not Godot 3. Linux-first
  (the game runs on a Linux PC hooked to the TV); export other platforms only
  when asked. Why Godot: the most Claude Code precedent and tooling, scenes are
  text, native Linux export, SDL gamepad mappings, a real pixel-perfect mode.
  Phaser is the pick only if the target is a browser.
- **Real pixel art, not a pixel-art look.** A native low-res canvas (default
  320x180, 16 px tiles), integer scaling only, nearest filtering, one Lospec
  palette per game, indexed PNGs. No downscaled AI images, no anti-aliasing,
  no sub-pixel movement on screen. See
  [references/pixel-art-pipeline.md](references/pixel-art-pipeline.md).
- **House repo conventions apply** (global CLAUDE.md): `git init -b master`,
  `CLAUDE.md` + `AGENTS.md` symlink, a Makefile with `start` plus the three
  tmux targets, `echo -e` for colours. Game-specific targets:
  `make start` (run), `make editor`, `make test` (GUT headless),
  `make sprites` (render + lint art), `make shot` (capture frames),
  `make export-linux`.
- **Godot is pinned per game and downloaded, not installed system-wide**:
  `make setup` fetches the official Linux x86_64 binary (and GUT) into a
  gitignored `.tools/`, so no sudo is needed and every machine runs the same
  version. Bump the pin deliberately.
- **Keyboard-only must always work, for testing AND for real play** (Oriol,
  2026-09-26). Every seat has a keyboard block on one shared keyboard, the
  join screen accepts keys like pads, and keyboard and pads can be mixed
  (dad on a pad, a kid on the keyboard's space bar). A game you can only
  test with three pads plugged in is a game the agent cannot test.
- **Third-party IP stays private.** Kids ask for Sonic, Minions and friends.
  Draw small homages ourselves (never ripped sprites) in a separate
  `private_pack/` the game loads only if present, excluded from exports. The
  shippable cast is original characters. The pack IS committed when the
  game's repo is private (Oriol, 2026-09-26: he expects a clone to have
  every character), and that repo then must never go public. Never publish,
  screenshot publicly or put the private pack in a portfolio entry. Ask
  which fan characters the kids want; do not stop at the ones the brief
  listed (Shadow was missed in PixelPals).
- **Popularity rule for third-party tools: >1k GitHub stars**, stated with the
  count. Below it = inspiration only. Our own scripts are exempt. A nicely
  executed TUI for tooling is welcome.
- **Family material is private.** Voice memos, photos or names of the kids
  never go into a game repo or anywhere public.

## Couch co-op with several gamepads

- **Assign roles by device id, never by pad order.** Linux pad order is not
  stable across boots or replugs. A join screen: each pad presses any button
  and takes the next seat; store `device_id -> role` in an autoload.
- **Hot-plug**: listen to `Input.joy_connection_changed`; an unplugged pad
  frees its seat without stopping the game, a replugged one rejoins.
- **Read input per device**: either filter `InputEvent.device` in
  `_input`/`_unhandled_input`, or create per-player actions at startup
  (`p1_fire`, `p2_fire`...) with `InputMap.action_add_event` bound to that
  device. Treat the keyboard as its own "devices" (one virtual device per
  keyboard block) in the same seat table, so every code path is shared.
- **Tests drive input without hardware**: inject `InputEventJoypadButton` /
  `InputEventKey` with `Input.parse_input_event()` or call the seat logic
  directly; a scripted-input demo mode lets `make shot` capture real
  gameplay frames unattended.
- **Mappings**: Godot uses SDL_GameControllerDB (1.8k stars), which covers
  most 8BitDo modes. For an unknown pad, add the line with
  `Input.add_joy_mapping()` or `SDL_GAMECONTROLLERCONFIG`; identify pads
  with `evtest` / `jstest`. 8BitDo pads expose different ids per mode
  (X-input / D-input / Switch), so pick one mode and note it in the game's
  README.

## Designing for young children (2-5)

- **No fail state.** A hit bounces, flashes and costs a few collectibles;
  there is no game over, no lives, no timer that can run out.
- **Asymmetric roles** (Super Mario Galaxy's Co-Star mode is the precedent:
  a second player involved without controlling a character). The parent owns
  the hard input (movement); the 5-year-old gets one or two buttons and at
  most 4 aim directions with generous aim assist; the 2-year-old gets "any
  button does something delightful" with a short cooldown and variety, and
  can never hurt the run.
- **Every press is answered** with sound, screen shake or a world reaction
  within a frame or two.
- **No text.** Icons, colours, characters. Menus navigable by the parent;
  a pause/exit combo only a parent can do.
- **Short sessions** (3-10 minutes) ending in a celebration screen.
- **Playtest the grey box** (coloured rectangles) on the couch before
  investing in art: which role was too hard, which too boring.

## Claude + Godot: the traps

- **Godot 3 drift.** Put "Godot 4.7+ only; no Godot 3 APIs (no `yield`,
  `KinematicBody2D`, `export var`...)" in the game's CLAUDE.md.
- **Hand-edited `.tscn`/`.tres` files break** (resource ids, `.uid` sidecars
  since 4.4). Build nodes in code, keep scenes to tiny shells, let the
  editor write scene files when a scene must be rich.
- **A fresh clone has no import cache** (`game/.godot/` is gitignored, the
  `.import` files are committed). `load("res://x.png")` then fails with
  "Unable to open file: res://.godot/imported/x.png-<hash>.ctex" for every
  asset, and GUT refuses to run ("Some GUT class_names have not been
  imported"). Two defences, both needed:
  - From source, read assets by bytes
    (`Image.load_png_from_buffer(FileAccess.get_file_as_bytes(p))`,
    `AudioStreamWAV.load_from_file`). Use `load()` only when
    `OS.has_feature("template")`, i.e. in an exported build.
  - Make every run/test target depend on an `ensure-import` that runs
    `godot --headless --import` when
    `.godot/global_script_class_cache.cfg` is missing.

  Always test a change on a clean clone
  (`git clone . <scratch>/clone && rm -rf <scratch>/clone/game/.godot`) before
  saying it runs on another machine.
- **Headless renders nothing.** `godot --headless` is for tests and
  scripts. For visuals capture frames: `--write-movie out.png` with a fixed
  `--quit-after`, under a real display or `xvfb-run`.
- **Verification loop before saying it works**: GUT tests for logic
  (input mapping, aim assist, "a hit never ends the game") + captured frames
  inspected. Show frames to the model **upscaled** (nearest, 4-8x) and
  cropped to the region in question: the model sees images in ~28 px
  patches, so a native 320x180 frame hides pixel-level problems.
- **Pixel-perfect settings** (`project.godot`):
  `display/window/size/viewport_width=320`, `viewport_height=180`,
  `window/stretch/mode="viewport"`, `window/stretch/aspect="keep"`,
  `window/stretch/scale_mode="integer"` (4.2+),
  `rendering/textures/canvas_textures/default_texture_filter=0` (Nearest),
  `rendering/2d/snap/snap_2d_transforms_to_pixel=true`,
  `rendering/2d/snap/snap_2d_vertices_to_pixel=true`.
  320x180 scales to 720p (x4), 1080p (x6), 1440p (x8), 4K (x12).

## What the model can and cannot do

Opus 5.5 does **not** output images or audio; art and sound come from code it
writes, and exactness from scripts that check it. Its vision and long
unattended runs did improve. Details, sources and consequences:
[references/opus-5-5.md](references/opus-5-5.md).

## Other skills and tools

Local skills:
- **content-creation** — trailers/brag videos of a game, contact-sheet
  discipline for anything visual.
- **catalan-writing** — if a game ever has ca/es/fr strings (UI text goes
  through i18n catalogs, never inline).
- **eu-law** — before publishing a game (privacy, children's data).
- **secrets-in-git** — store keys (itch.io, Steam) if we ever publish.

External, over the bar (read for ideas; star counts checked 2026-09-26):
- [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) (5.8k) —
  MCP server: launch editor, run the project, capture debug output, create
  scenes. The one tool worth installing per project (`.mcp.json`).
- [htdt/godogen](https://github.com/htdt/godogen) (7k) — whole Godot games
  from a prompt; read its visual-QA loop (judge the running game, not the
  compile) and its bundled Godot 4 API docs idea. Needs C# and paid APIs; not
  our shape.
- [gamedev-skills/awesome-gamedev-agent-skills](https://github.com/gamedev-skills/awesome-gamedev-agent-skills)
  (1.1k, young) — 73 generic skills, 15 for Godot; copy ideas, do not
  install the lot.
- [Pixelorama](https://github.com/Orama-Interactive/Pixelorama) (10k, free) and
  [Aseprite](https://github.com/aseprite/aseprite) (39k, paid or build from
  source) — pixel editors for hand touch-ups.

Below the bar — inspiration only: aseprite MCPs (diivi/aseprite-mcp 598,
willibrandon/pixel-mcp 145), pixellab-mcp (42, paid service),
Randroids-Dojo/Godot-Claude-Skills (45, GdUnit4/PlayGodot testing ideas),
jwynia/agent-skills `godot-asset-generator` (160), godot-mcp-pro (608).
