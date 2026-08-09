# Adding paints to the catalogue

The built-in Vallejo catalogue lives in
`src/mini_highlight_advisor/data/vallejo_paints.json`. Grow it by hand — add
one entry per paint to the `paints` array. No code change is needed; the app
picks up new entries on the next run.

## Schema

The file is a single JSON object:

```json
{
  "_note": "...",
  "paints": [
    {"name": "Neutral Grey", "brand": "Vallejo", "range": "Model Color", "hex": "#6d7173"}
  ]
}
```

Per entry:

- `name` — **required**. Must be **unique** across the whole file (the picker
  resolves paints by name and takes the first match, so duplicates break it).
- `hex` — **required**. Must be `#rrggbb` — a `#` followed by exactly six
  hex digits (`0-9`, `a-f`, `A-F`). Example: `#6d7173`. Case does not matter.
- `brand` — optional. Use `"Vallejo"` (the only catalogue brand for now).
- `range` — optional. e.g. `"Model Color"` or `"Game Color"`.

## Copy-paste example row

```json
    {"name": "Gory Red", "brand": "Vallejo", "range": "Game Color", "hex": "#7a1f1f"},
```

Paste it inside the `paints` array. Mind the commas: every entry except the
last needs a trailing comma.

## If you make a mistake

The catalogue is validated when the app loads. A bad entry produces a clear
error that names the offending paint (or its index if `name` is missing), so
you can find and fix it — a malformed hex, a missing `name`/`hex`, or a
duplicate name will each be reported rather than crashing or showing a wrong
colour.

## Scope

Hexes are approximate screen-swatches, not spectrophotometer-accurate. Target
coverage is Vallejo Model Color + Game Color. Other lines (Air, specialty) are
out of scope.
