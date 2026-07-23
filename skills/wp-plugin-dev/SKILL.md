---
name: wp-plugin-dev
description: Build, version and distribute WordPress plugins — especially private/client plugins shipped as a zip (no wordpress.org listing). Use when creating a WP plugin from scratch, wrapping a JS widget/embed as a plugin, adding a settings page/shortcode/block, asked "how do users update my plugin by uploading a new zip without duplicating it", wiring self-hosted auto-updates (Update URI header, update_plugins_{hostname}, plugin-update-checker), fixing "destination folder already exists", or reviewing plugin security (nonces, sanitize/escape, capability checks). Covers plugin identity rules (folder + header), the WP 5.5 zip-replace flow, the WP 5.8 Update URI header against wp.org hijacking, release checklists, and the security five-step for every handler.
---

# WordPress plugin development and zip-based updates

Rules that matter when the plugin is distributed as a zip handed to clients
(private/client plugins), plus the general must-knows. Verified against WP
core behavior and the official plugin handbook as of 2026-07.

## Plugin identity — what makes an update an UPDATE and not a duplicate

WordPress identifies a plugin by its **directory name + main PHP file**
(`plugin_basename(__FILE__)` → `my-plugin/my-plugin.php`). Everything about
clean updates follows from keeping that identity stable forever:

1. **The zip must contain exactly one top-level folder** named after the
   plugin slug (`my-plugin/`), with the main file inside it. A zip with loose
   files at the root makes WP create a random-suffix folder
   (`my-plugin-xhfuif/`) and later "Plugin file does not exist" errors.
2. **Never rename the folder or the main file between releases.** A renamed
   folder is a different plugin: it installs alongside the old one
   (duplicate), with both trying to register the same hooks.
3. **Bump the `Version:` header every release.** WP shows "You have version
   X installed, uploaded version is Y" and compares with `version_compare()`
   — plain `1.4.2`-style versions; suffixes like `-beta1` sort BEFORE the
   bare version (`1.4.2-beta1 < 1.4.2`), which is correct but surprises people.

### The zip-update flow (no duplication, since WP 5.5)

Plugins → Add New → Upload Plugin → choose the new zip → WP detects the
already-installed folder and shows a comparison screen with a **"Replace
current with uploaded"** button. That is an in-place upgrade: same folder,
options preserved, activation state preserved. Tell clients exactly this
path. If WP instead says only "destination folder already exists" with no
replace button, the zip structure is wrong (folder-name mismatch or nested
twice) — fix the zip, don't have the user delete the plugin.

Deactivate/delete is NOT needed for updates. Deleting runs `uninstall.php`
(data loss) — warn clients never to "update" that way.

### Build the release zip deterministically

```bash
# from the repo: the folder inside the zip IS the identity — pin it
VERSION=$(grep -oP 'Version:\s*\K[0-9.]+' my-plugin/my-plugin.php)
zip -r "my-plugin-${VERSION}.zip" my-plugin/ -x '*.git*' -x '*node_modules*'
```

The zip filename can carry the version (helps humans); WP ignores it — only
the folder inside and the `Version:` header matter.

## Main-file header — the fields that do something

```php
<?php
/**
 * Plugin Name:       My Plugin
 * Description:       One line, shown in the plugin list.
 * Version:           1.4.2
 * Requires at least: 6.2
 * Requires PHP:      8.1
 * Author:            You
 * License:           GPL-2.0-or-later
 * Text Domain:       my-plugin
 * Update URI:        https://updates.example.com/my-plugin
 */
if ( ! defined( 'ABSPATH' ) ) exit; // no direct access
```

- **`Update URI` (WP 5.8+) is mandatory for private plugins.** Without it, a
  same-slug plugin on wordpress.org can silently overwrite yours through the
  normal update system (CVE-2021-44223). Any value not matching
  `https://wordpress.org/plugins/{slug}/` stops wp.org updates; setting it
  also activates the `update_plugins_{$hostname}` filter for self-hosted
  updates. Use `false` as the value to simply opt out of all update checks.
- `Requires at least` / `Requires PHP` gate installation and updates.
- `readme.txt` (with `Stable tag`) only matters for wordpress.org listings —
  a private plugin doesn't need it, but a short one helps the "View details"
  modal if you serve metadata yourself.

## Self-hosted auto-updates (optional upgrade from manual zips)

Manual zip-replace is fine for a handful of clients. For fleets, make WP
check YOUR server. Two proven routes:

### Route A — library: YahnisElsts/plugin-update-checker (fastest, 1.6M+ installs)

```php
require __DIR__ . '/vendor/plugin-update-checker/plugin-update-checker.php';
use YahnisElsts\PluginUpdateChecker\v5\PucFactory;
PucFactory::buildUpdateChecker(
    'https://updates.example.com/my-plugin/info.json',
    __FILE__,
    'my-plugin'          // must equal the folder slug
);
```

Serve a static `info.json` + the release zip; the library handles the
transient plumbing and "View details". Also does GitHub/GitLab releases
directly (private repos via access token).

### Route B — hand-rolled with core hooks (no dependency)

Host `info.json`:

```json
{
  "name": "My Plugin", "slug": "my-plugin", "version": "1.5.0",
  "download_url": "https://updates.example.com/my-plugin/my-plugin-1.5.0.zip",
  "requires": "6.2", "requires_php": "8.1", "tested": "6.7",
  "last_updated": "2026-07-24 10:00:00",
  "sections": { "description": "...", "changelog": "<h4>1.5.0</h4><ul><li>...</li></ul>" }
}
```

Hook `update_plugins_{$hostname}` (the hostname from your `Update URI`) to
report a newer version, and `plugins_api` (slug-matched!) for the details
modal. Gotchas that bite:

- **Cache the remote fetch in a transient (~6–12 h).** The update check runs
  on many admin pageloads; uncached = you hammer your own server.
- `plugins_api` fires for EVERY plugin — return `$result` unchanged unless
  `$args->slug === 'my-plugin'`, or you break other plugins' modals.
- Compare all three: `version_compare(installed, remote, '<')` AND WP
  version AND PHP version before offering the update.
- The `package`/`download_url` zip must follow the same one-folder rule.
- Slug vs basename: transient entries are keyed by
  `my-plugin/my-plugin.php` (basename), while `plugins_api` uses `my-plugin`
  (slug). Mixing them up = update never appears.

## Security — the five-step for every handler

Every form handler, AJAX callback, REST route and admin action, in order:

1. **Capability**: `current_user_can( 'manage_options' )` (or the narrowest
   cap that fits).
2. **Nonce**: `wp_nonce_field( 'my_action' )` in the form,
   `check_admin_referer( 'my_action' )` (or `wp_verify_nonce`) in the handler.
3. **Sanitize input**: `sanitize_text_field`, `sanitize_email`, `absint`,
   `sanitize_key`, `wp_kses_post` for rich text. Never trust `$_POST` raw.
4. **Prepared SQL** if you touch `$wpdb`: `$wpdb->prepare( '... %s', $v )`.
   (Prefer the options/post-meta APIs — they handle this.)
5. **Escape output at print time**: `esc_html`, `esc_attr`, `esc_url`,
   `wp_kses_post`. Escaping late beats trusting stored data.

Plus: `if ( ! defined( 'ABSPATH' ) ) exit;` at the top of every PHP file, and
prefix (or namespace) every function/option/hook — the global namespace is
shared with every other plugin.

## Structure and lifecycle essentials

- **Prefix everything**: functions `myplugin_`, options `myplugin_settings`,
  hooks `myplugin/thing_happened`. Collisions are the #1 rookie bug.
- **Activation/deactivation**: `register_activation_hook` for one-time setup
  (schema via `dbDelta`, default options, rewrite flush);
  `register_deactivation_hook` to clear crons/rewrites. Neither runs on
  UPDATE — gate schema changes on a stored version option checked on
  `admin_init` (`if get_option('myplugin_db_version') < CURRENT → migrate`).
- **`uninstall.php`** (preferred over the hook): delete options, tables,
  crons. Runs on delete, not deactivate.
- **Settings**: for one town/client-key style config, a simple
  `add_options_page` + Settings API (`register_setting` with a sanitize
  callback) beats a framework. Store one array option, not 20 scalars.
- **Enqueue, never echo, scripts**: `wp_enqueue_script( 'my-plugin', $url,
  [], MY_PLUGIN_VERSION, [ 'in_footer' => true, 'strategy' => 'defer' ] )` —
  passing the plugin version busts caches on every release. For external
  embeds, `wp_enqueue_script` with a remote URL + `wp_script_add_data` /
  the `script_loader_tag` filter to add data-* attributes.
- **Shortcode + block**: ship the shortcode (`add_shortcode`) first — it
  works everywhere including classic editors and page builders; add a
  Gutenberg block wrapper (usually a dynamic block rendering the same
  callback) when the audience uses the block editor.
- **i18n**: `Text Domain` header matching the folder slug + `__()/esc_html__()`
  with literal strings. Since WP 4.6 wordpress.org plugins auto-load
  translations; private plugins call `load_plugin_textdomain` on `init`.
- **Fail soft on the front end**: a client-site plugin must never white-screen
  the site. Guard remote calls with `wp_remote_get` + error checks; if your
  backend is down, render nothing rather than an error.

## Release checklist (zip-distributed plugin)

- [ ] `Version:` bumped in the main-file header (single source of truth;
      grep-able for the zip script)
- [ ] Changelog entry (readme.txt or info.json `sections.changelog`)
- [ ] Zip contains exactly `my-plugin/` at the root, same folder name as
      every previous release
- [ ] `Update URI` header present (private plugins)
- [ ] Tested: fresh install on a clean WP, AND zip-upload over the previous
      version → "Replace current with uploaded" appears and settings survive
- [ ] If self-hosted updates: `info.json` version + download_url updated
      LAST (after the zip is live), transient cache TTL respected

## Reference skills (for structure/coverage ideas — do not copy)

- WordPress/agent-skills (official; `wp-plugin-development`, router pattern,
  references/ + scripts/ layout)
- Automattic/agent-skills and wordpress.com "Agent Skills" docs
- wpacademy/wordpress-dev-skills (wp.org guideline compliance angle)
- levantoan/DevVN-WordPress-Skills (license management + auto-update angle)
