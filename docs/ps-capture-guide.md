# Photometric Stereo Capture Guide

This guide tells you how to photograph a primed miniature so that the highlight advisor can recover its fine surface detail (helmet ridges, pauldron tops, recesses) and plan your highlights accordingly.

**What you need:**
- One primed mini (grey or black primer)
- A phone camera
- A bright hand-held light source (desk LED, phone torch, or lamp)
- A tripod or stands to keep the camera and mini fixed in place
- A high-contrast background (plain fabric or wall)
- A plain background so the masking tool can isolate the mini cleanly

**Key principle:** You'll move the light around the fixed mini while the camera stays still. This teaches the computer about surface relief — the opposite of flash photography, which hides it.

---

## Checklist: Before You Shoot

- [ ] **Phone on a stand.** Brace your phone with a tripod, book stack, or stand. The phone must not move between shots.
- [ ] **Mini positioned clearly.** Place it on a neutral base with the camera roughly 30–50 cm away, at a slight downward angle (like looking at the mini on a table).
- [ ] **Background plain and high-contrast.** White sheet, black cloth, or plain wall — nothing busy. The masking tool will use this edge to cut out the mini cleanly.
- [ ] **Light source ready.** A bright LED, phone torch (held by hand or on a clip), or desk lamp will do. Dim the room lights if possible so one clear light direction dominates each shot.
- [ ] **Exposure locked.** If your phone has an exposure lock feature, use it. All shots should be similarly bright — no HDR, no automatic adjustment between frames.
- [ ] **Flash off.** Turn off the camera flash.

---

## The Lighting Setup

Move your light to **6–8 different positions** around the mini. Aim for even coverage so no part of the mini stays dark in all shots and no part gets blown out in all shots.

**Example light positions:**
- Upper left
- Upper right
- Left (at ~eye level to the mini)
- Right (at ~eye level to the mini)
- Directly above (top-down)
- Below and behind (raking at a low angle)
- Front-lower-left
- Front-lower-right

The idea: every ridge, recess, and surface should catch light from several different directions across the set. Avoid one-sided lighting; vary the angle.

---

## During the Shoot

1. **Position the light.** Place it at your first position — say, upper left, maybe 20–30 cm from the mini.
2. **Compose and lock the camera.** Ensure the mini fills most of the frame but is fully visible and not cut off. Do not move the camera.
3. **Take a shot.** Photograph the lit mini. Make sure it's sharp and the lighting is clear (not washed out by flash or shadow).
4. **Move only the light.** Reposition the light to your next angle. **The mini and camera do not move.**
5. **Shoot again.** Repeat until you have **6–8 photos** covering all the light positions you planned.

---

## Quality Checks (On Phone, Before Uploading)

- **Lighting variation:** Each shot should look noticeably different — the shading should shift as the light moves. If all 6 shots look the same, your light is too similar or too weak.
- **No blown-out areas in all shots:** If the tip of a sword or a helmet crest is white in *every* shot, the light was too consistent or too bright. Try angling it differently.
- **No black areas in all shots:** If a recess is dark in *every* shot, move the light to angle into that crevice at least once.
- **Camera stability:** Flip between the first and last shot on your phone screen — the mini should be in the same position. If it drifts significantly, you may need to repeat the shoot with a firmer brace.
- **No motion blur:** Each shot should be sharp. Stable framing + indoor lighting helps; use your phone's normal (not portrait) mode.

---

## For Dark Primers (Black)

Black primer has less light to work with — use a brighter light source and a slightly longer exposure (a bit slower shutter, or a brighter LED). The algorithm needs enough shading variation to read the surface; if the mini is too dark overall, the detail gets lost.

**Pro tip:** If you can, shoot two separate sets — one of a grey-primed test mini and one of your actual black-primed mini. The grey set is easier to diagnose; the black set is the real goal.

---

## Background and Masking

The tool will automatically remove the background using the contrast between the mini and the background. A plain, high-contrast background (white sheet on a dark mini, dark sheet on grey mini) makes this reliable. Avoid shadows falling on the background behind the mini.

---

## After You Shoot

1. **Keep the frames.** Save all 6–8 shots in a folder named something like `black_mini_shots/` or `grey_mini_shots/`.
2. **Name them consistently.** Rename them to `L_01.png`, `L_02.png`, `L_03.png`, etc., in the order you took them. (The tool reads them in sorted order.)
3. **Import into the app.** In the highlight advisor:
   - Choose **Import normal map (photometric stereo)**.
   - Upload the frames folder or select the frames.
   - The tool will:
     - Automatically mask and align the frames.
     - Run the recovery algorithm on the cloud or your local machine.
     - Produce a normal map encoding the surface relief.
   - Check the report: it should say you have **at least 4 frames** after filtering (the tool drops frames with masking issues or weak lighting variation).

4. **If frames are dropped:** The tool may discard 1–2 frames if the background masking was inconsistent or the lighting was too similar to a nearby frame. **Shoot 6–8 frames, not 4–5**, so that losing a couple still leaves you above the 4-frame minimum.

---

## Cross-Reference

For details on running the recovery tool and interpreting the output, see [`tools/README-ps.md`](../tools/README-ps.md).

---

## Summary: The Load-Bearing Rules

1. **Fixed pose:** Camera and mini do not move. Only the light moves.
2. **One moving light:** 6–8 shots, each from a different angle, covering the full surface.
3. **Shading everywhere:** No dark areas in all shots; no blown-out areas in all shots.
4. **Locked exposure:** Consistent brightness across all frames, no flash.
5. **Shoot extra:** Aim for 6–8 frames so losing 1–2 to masking quirks still leaves enough data.
6. **Plain background:** High-contrast, consistent background for reliable masking.

Follow these, and you'll give the algorithm the data it needs to separate the mini's shape from its color.
