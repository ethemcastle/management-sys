# 04 · Design Tokens

**HIGH fidelity — match these exactly.** Copy this straight into `styles/_tokens.scss`. All component
colors must reference these custom properties; never hardcode hex in components. Toggle themes by
setting `data-theme="light|dark"` on `<html>`.

## Fonts
- **UI:** `Hanken Grotesk` (weights 400/500/600/700/800).
- **Mono:** `JetBrains Mono` (weights 400/500/600/700) — used for issue keys, story points, PR
  numbers, branch names, and any "code-ish" value.
- Load via Google Fonts:
  `https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap`

## Color tokens (SCSS / CSS custom properties)

```scss
:root, [data-theme="light"] {
  --bg:#F4F4F1; --surface:#FFFFFF; --surface-2:#F0F0EC; --surface-3:#E7E7E1;
  --border:#E5E4DF; --border-2:#D4D3CC;
  --text:#191917; --text-2:#63625B; --text-3:#95948B;
  --accent:#5A50E1; --accent-fg:#FFFFFF; --ai:#B45AF2;
  --success:#2E9E5B; --success-soft:#E4F3EB;
  --warning:#C0820A; --warning-soft:#F6EFDC;
  --danger:#D95340;  --danger-soft:#F9E9E6;
  --info:#3B7DD8;    --info-soft:#E7F0FB;
  --radius:12px; --pad:16px;
  /* derived accents */
  --accent-soft: color-mix(in oklab, var(--accent) 12%, transparent);
  --accent-line: color-mix(in oklab, var(--accent) 30%, transparent);
  --ai-soft:     color-mix(in oklab, var(--ai) 9%, transparent);
  --ai-line:     color-mix(in oklab, var(--ai) 26%, transparent);
}

[data-theme="dark"] {
  --bg:#0C0D10; --surface:#141519; --surface-2:#1C1D22; --surface-3:#25262C;
  --border:#26272E; --border-2:#35363E;
  --text:#ECECEE; --text-2:#9E9EA6; --text-3:#6B6C74;
  --accent:#7E77FF; --accent-fg:#FFFFFF; --ai:#C77DFF;
  --success:#43B26E; --success-soft:#132A1E;
  --warning:#D9A23C; --warning-soft:#2A2113;
  --danger:#E86A56;  --danger-soft:#2E1A17;
  --info:#5A9BEB;    --info-soft:#132133;
  --accent-soft: color-mix(in oklab, var(--accent) 22%, transparent);
  --accent-line: color-mix(in oklab, var(--accent) 42%, transparent);
  --ai-soft:     color-mix(in oklab, var(--ai) 16%, transparent);
  --ai-line:     color-mix(in oklab, var(--ai) 34%, transparent);
}
```

### Token meaning
- `--bg` app background · `--surface` cards/sidebar/topbar · `--surface-2/3` insets, hovers, tracks.
- `--border` hairlines · `--border-2` stronger dividers, dashed placeholders.
- `--text` primary · `--text-2` secondary · `--text-3` tertiary/muted.
- `--accent` brand/primary action · `--ai` all AI affordances (never mix the two).
- `--success/warning/danger/info` + their `-soft` fills for pills, badges, status.
- `color-mix(... oklab ...)` derives translucent fills — supported in all current browsers; if you
  must support older ones, precompute equivalents.

## Semantic color coding (must match)

**Issue type** (badge letter + fill):
`story` S `#2E9E5B` · `bug` B `#D95340` · `task` T `#3B7DD8` · `epic`/Feature E `#8B5CF6`.

**Priority** (0–3) label + color, rendered as a 3-bar glyph (heights 6/9/12px, 3px wide):
`0 Low #9A998F` · `1 Medium #C0A227` · `2 High #E8833A` · `3 Urgent #D95340`.
Bar rule: bar1 always the priority color; bar2 colored if priority≥1 else `--border-2`; bar3 colored if ≥2.

**Status** pill label + color:
`backlog/todo #9A998F` · `inprogress #3B7DD8` · `review #C0A227` · `done #2E9E5B`.
Pill fill = `color-mix(in oklab, <color> 12%, transparent)`, text = `<color>`.

**PR state** dot: `open #3B7DD8` · `draft #9A998F` · `merged #8B5CF6`.
**CI checks** dot/icon: `passing #2E9E5B` · `failing #D95340` · `pending #C0A227` (pending spins).
**Review state:** `approved #2E9E5B` (check) · `pending #C0A227` (clock) · `changes #D95340` (x).

**Labels** (name → color): frontend `#3B7DD8` · backend `#2E9E5B` · api `#B45AF2` · infra `#E8833A`
· design `#D95340` · urgent `#D95340` · mobile `#0E7C86` · docs `#9A998F`. Chip fill = color at ~13% alpha, text = color.

**Avatars:** 2-letter monogram, per-member solid background color (see `07_SEED_DATA.json`), white
text, JetBrains Mono ~9.5–11px, rounded 7–9px (or 50% on the board). Unassigned = 1.5px dashed `--border-2` circle.

## Type scale (observed in design)
| Use | Size / weight |
|-----|----------------|
| Page H1 (dashboard greeting, issue title) | 24–26px / 800, letter-spacing −0.02em |
| Card / section title | 14–14.5px / 700 |
| Body | 13–14px / 400–500, line-height ~1.55 |
| Secondary / meta | 11.5–12.5px / 500–600, `--text-3` |
| Micro (uppercase section labels) | 10–11px / 700, letter-spacing 0.06–0.09em, uppercase |
| Mono values (keys, points, PR#) | 10.5–12.5px, JetBrains Mono |
| Big metric numbers | 27–30px / 700 mono, letter-spacing −0.02em |

## Spacing / radius / shape
- Base unit 4px. Common gaps 5/7/9/11/14/16px. Card padding 11–18px. View padding 20–28px.
- Radius: cards `12px` (`--radius`, tweakable 6–20) · pills/badges 6–8px · buttons 8–9px · avatars 7–9px.
- Borders: 1px hairlines in `--border`. Cards get a faint shadow `0 1px 2px rgba(0,0,0,.03)`, lifting
  to `0 4px 14px rgba(0,0,0,.07)` on hover.
- Sidebar width **252px**; top bar height **56px**; issue-detail right rail **344px**; board column **300px**.

## Motion
- `fade` in views: `translateY(7px)+opacity` 0.35–0.4s ease.
- Spinners: 0.8s linear rotate. Thinking dots: staggered blink 1.2s. AI panel: slide-in from right
  0.28s `cubic-bezier(.22,1,.36,1)`. Keep transitions subtle (120–200ms) on hovers.

## Tweakable knobs (were exposed in the prototype; wire as user/workspace settings)
- **accent** (options `#5A50E1`, `#2E9E5B`, `#0E7C86`, `#D95340`, `#C2410C`) · **theme** (light/dark)
  · **radius** (6–20px) · **density** (comfortable/compact) · **default role** (developer/po).
