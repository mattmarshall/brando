# brando portrait — the canonical mark

brando's logo/avatar is a vectorized portrait of **Marlon Brando** (the namesake).
It is a traced vector **asset** — NOT a parametric `marklib` mark — so it is committed
here directly. (The marionette generators in `selfbrand/` remain as the `marklib`
pipeline dogfood, exercising brando's public rules on a parametric mark.)

- `brando_portrait.svg` — the vector (~180 path ops, ~9.7 KB).
- `brando_avatar_{1024,512}.png` — the canonical avatar: black portrait on a cream
  rounded-square (`#ECE7DA`). **This is the repo/org avatar.**
- `brando_avatar_inkbg_1024.png` — alternate: cream portrait on ink (`#15161A`).
- `brando_portrait_transparent_1024.png` — portrait on transparent.

## Regeneration (from an AI-generated high-contrast stencil PNG)

Non-hermetic (uses imagemagick + potrace + svgo + inkscape); the outputs are committed.

```sh
# 1. threshold to a clean bilevel bitmap (ink -> black)
magick stencil.png -resize 200% -colorspace Gray -threshold 60% -type bilevel b.pbm
# 2. trace with curve optimization (smooth, minimal segments; corners preserved)
potrace b.pbm --svg --turdsize 10 --alphamax 1.0 --opttolerance 0.7 -o raw.svg
# 3. simplify: round coords, merge, drop redundant points
svgo --multipass -p 1 raw.svg -o brando_portrait.svg
# 4. composite the avatar: portrait centered on a rounded-square bg
#    creambg  = black portrait on #ECE7DA   (canonical)
#    inkbg    = #ECE7DA portrait on #15161A (alternate)
```
