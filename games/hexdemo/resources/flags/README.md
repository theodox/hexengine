# Hexdemo example flag graphics

Small SVG faction flags for UI skinning demos (turn banner, optional unit art).

| File | Faction | Notes |
|------|---------|--------|
| `union_34star.svg` | Union | Simplified 34-star U.S. flag (1861–1863) |
| `confederate_battle.svg` | Confederate | Square Army of Northern Virginia battle flag |

Referenced from the phase turn banner via `<img src="...">` in
`ui_markup.render_phase_banner_html()` (URLs under `/pack/hexdemo/flags/` when using the dev static server).
Sizing is controlled by `--hexdemo-turn-banner-flag-w` / `-h` on
`.hexdemo-turn-banner` in `resources/ui.css` (keep `TURN_BANNER_FLAG_*_PX` in
`ui_markup.py` in sync for the `<img width height>` fallback).

Historical flag designs are not copyrightable; these files were authored for Hexdemo
at small display sizes. Higher-fidelity versions are on Wikimedia Commons (public domain),
e.g. [Flag of the United States (1861–1863).svg](https://commons.wikimedia.org/wiki/File:Flag_of_the_United_States_(1861%E2%80%931863).svg)
and [Battle flag (1-1).svg](https://commons.wikimedia.org/wiki/File:Battle_flag_of_the_Confederate_States_of_America_(1-1).svg).

**Unit emblem example** — in `scenario.toml`:

```toml
[[unit_graphics]]
type = "union_leader"
svg_file = "flags/union_34star.svg"
render = "image"
```

Use `confederate_battle.svg` for Confederate leaders; keep `viewBox` aspect in mind when
placing inside `unit_template.svg` (100×100 art box).
