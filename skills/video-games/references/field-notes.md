# Field notes

Dated lessons from real games, newest first. One entry per lesson: what
happened, the rule it produced, and where the rule now lives.

## 2026-09-27 — Going public: purging the fan art from history

- Oriol made the monorepo public. The fan-character packs (Sonic, Minions,
  Mario...: 424 files in 14 games, 918 paths across history) had been
  committed while it was private. Steps that worked:
  1. Audit: every IP file sat under `private_pack/` or `art_src/private/`;
     the public manifests and contact sheets (looked at) showed only the
     original cast; text mentions of the names are harmless.
  2. `git rm -r --cached` those dirs, add `**/private_pack/` and
     `**/art_src/private/` to `.gitignore`, and prove a clean clone passes
     every game's tests without the pack.
  3. Back up the full history first (`git bundle create <outside>.bundle --all`).
  4. `uvx git-filter-repo --force --invert-paths --path-glob
     'games/*/game/private_pack/*' ...` (including the pre-monorepo paths).
  5. **Delete and recreate the GitHub repo**, then push: a force-push leaves
     the old commits fetchable by SHA, and they become public with the
     repo. Needs `gh auth refresh -s delete_repo` (a browser step for the
     user). Verified afterwards: `gh api repos/<o>/<r>/commits/<old sha>`
     answers 422.
- **Trap: `git filter-repo --force` resets the working tree and discards
  uncommitted changes.** My doc edits and the `.gitignore` lines were
  unstaged (the earlier `git commit` without `-a` took only the
  `rm --cached` deletions), so the rewrite silently threw them away and the
  private dirs showed as untracked, one `git add .` from being re-committed.
  Rule: before filter-repo, `git status` must be empty; commit with
  `git add -u` + explicit paths, and check the ignore rules exist right
  after the rewrite.

## 2026-09-27 — The TV launcher and the pad quit combo

- Built `launcher/` in the monorepo: a 1080p Godot carousel (canvas_items
  stretch) that discovers `games/*/game/project.godot`, launches each game
  as its own process (`OS.create_process` + `OS.is_process_running` poll),
  waits underneath it and restores on exit. Verified by a real launch under
  xvfb (`make -C launcher launch-test`: PixelPals ran 3.7 s and the
  launcher came back on the same card) and a fresh-cache run.
- **The games had no way to quit from a pad.** Added, additively, to the
  shared `players.gd`: hold Back/Select + Start 1.5 s (any pad) or Ctrl+Q.
  It runs on a `PROCESS_MODE_ALWAYS` watcher node, so paused games quit too,
  and a hold that started before the app (or before re-enabling) arms only
  after a release, so the combo that closed a game cannot also close the
  launcher. All 16 game suites stayed green. Rule now in the monorepo
  CLAUDE.md: never bind Back+Start to anything else.
- **Fonts on a 1080p UI:** `SystemFont` with MSDF on variable system fonts
  (Adwaita Sans/Inter) rendered letters with holes, and a thick outline on
  big text showed the overlapping contours as ghost strokes. Plain
  rasterisation plus a drop shadow is clean.
- **`window/size/window_width_override` beats `--resolution`**: movie
  captures came out 1280x720 instead of 1920x1080. Keep the override out of
  a project that is captured at another size; pass the dev window size on
  the command line.
- **Parallel `xvfb-run -a` can race** for a display and cut a capture
  short (2 of 14 in one run). The covers tool retries a capture that is
  shorter than the frame it needs.
- **Demo captures are not deterministic** (games randomise), so a picked
  frame index shows a slightly different moment each run: look at the
  result, and crop only when the subject stays put (Train Conductor).
- **Pixel covers on a non-pixel UI:** pre-scale the image by a whole factor
  with nearest filtering, then draw with mipmapped linear filtering. At the
  focused size (exactly 2x for 320x180) the pixels are crisp, and the small
  side cards do not shimmer.
- A `Control`'s own `_draw()` paints under its children: an icon drawn on a
  card vanished behind the cover `TextureRect`. Draw overlays on a child
  Control added last.

## 2026-09-27 — 12 games built in parallel, one agent per game

- Oriol asked for every plan to be implemented in full. Twelve background
  agents ran at once, each with the same brief:
  - write only inside `games/<slug>/`, with `shared/` read-only (frozen
    after one last helper, `dir4_just_pressed`, was added first);
  - no commits;
  - copy freely from PixelPals;
  - "done" means the game's tests pass, every screen is captured AND
    looked at, and a clean-cache (`rm -rf game/.godot`) re-run is green.
- **Result:** all 12 came back playable in 26 to 49 minutes each. The
  coordinator re-verified each one independently (a wiped cache, its
  tests, one capture it looked at itself) and committed it with a
  path-limited `git commit -- games/<slug>`, while the others kept
  working. The root `make test` then passed 793 tests across 13 games.
- **Zero collisions**, because ownership was by path and `shared/` was
  frozen. The cost is duplication: 12 copies of the synth, the sprite
  renderer and the menu screens, plus 7 missing shared APIs, each with a
  local stand-in. The agents each proposed a shared diff in their report,
  and the coordinator collected them into one backlog
  (`docs/ideas.md`). Do that extraction as its own pass, not mid-build.
- **What the agents learned the hard way** is now in SKILL.md "Claude +
  Godot: the traps": no 2D MSAA in Compatibility, `-s` scripts and
  autoloads, the dummy audio driver, BPM versus sample rate, physics
  determinism, low-res 3D.
- **The demo driver was each game's real test harness:** the Zoo Keeper
  capture found a dancing animal refusing food, which a unit test had
  missed.

## 2026-09-26 — PixelPals becomes the couch co-op monorepo

- Restructured into `games/<slug>/` + `shared/`, with `git mv` so history
  is kept. Shared autoloads became symlinks
  (`game/autoload/players.gd -> ../../../../shared/godot/autoload/players.gd`).
  Godot 4.7 follows them fine, and the fresh-clone tests and captures
  passed.
- Trap: the `.gitignore` entry `game/.godot/` was path-anchored, so after
  the move the import cache (~400 files) got staged into the commit. Caught
  before pushing and amended. Rule: ignore Godot's cache as `.godot/`
  (unanchored) from day one, and read `git status` before every commit
  that follows a move.
- The plans for 12 more games were written by 3 parallel agents, 4 plans
  each, all to one fixed PLAN.md structure (roles table with pad and
  keyboard, no-fail rules, how each asset is made without image output,
  reuse, milestones, tests, open questions).

## 2026-09-26 — PixelPals: crash on the first real run (fresh clone)

- Oriol's first run printed dozens of "Unable to open file:
  res://.godot/imported/robotnik.png-….ctex" errors. `art.gd` trusted
  `ResourceLoader.exists()`, which is true whenever the committed `.import`
  file exists, even though the imported cache it points at was never
  built. It passed every in-session check because this checkout had been
  imported. Fix and rule: SKILL.md "A fresh clone has no import cache".
- Near miss while reproducing it: on this machine `cp` and `rm` are
  interactive aliases. An unanswered `cp` prompt broke an `a && cd clone &&
  …` chain, so the following `git stash` and `rm -rf game/.godot` ran in the
  REAL repo. Nothing was lost (the stash was popped). Rule: use
  `command cp -f` / `command rm -rf`, and put destructive steps behind an
  explicit `cd <abs path> || exit 1` on their own line.

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
