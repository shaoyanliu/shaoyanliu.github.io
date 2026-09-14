# SL monogram

Shaoyan Liu selected concept C from the favicon studies on September 14, 2026.
The interlocking SL uses a navy mark and a light background for contrast in both
light and dark browser tab bars.

- `sl-monogram-master.png`: original artwork from the built-in `image_gen` tool.
- `../img/favicon.png`: 32 × 32 PNG.
- `../img/favicon-64.png`: 64 × 64 PNG.
- `../img/apple-touch-icon.png`: 180 × 180 PNG.
- `../../favicon.ico`: 32 × 32 ICO fallback.

The PNG sizes were exported with macOS `sips`; the ICO fallback embeds the 32 px
PNG without changing its pixels. Shared favicon links live
in `_includes/favicon.html`; increment their `v=sl1` revision when changing the
artwork so browsers can refresh their cached icons.

## Generation prompt

Reference: the C / SL column in the five-concept favicon comparison board.
Generated using the built-in image tool, not the API/CLI fallback.

> Create the final single square favicon artwork from the SELECTED CONCEPT C / SL in the center column of the reference board. Preserve that exact distinctive bold interlocking uppercase SL monogram: the sweeping S curve and the strong shared upright/horizontal L foot. Do not replace it with ordinary separate typeset letters. Isolate ONLY the SL mark, no other columns, labels, heading, previews, or text. Flat solid Penn State navy #13294B mark, sharp geometric edges, absolutely no gradients, shadows, texture, bevel or 3D. Place it centered on a plain solid white square canvas, square image aspect ratio. Make the monogram large, occupying approximately 88 percent of the canvas width while preserving the reference mark's aspect ratio, with even small safety margins and no clipping. White background must be fully opaque, not transparent. This is a finished production favicon image, NOT a presentation board and NOT a browser mockup. Keep the broad S and L shapes thick and the curved negative space clean enough to read when reduced to 16 or 32 pixels. Output just this one clean white-square-and-navy-SL icon.
