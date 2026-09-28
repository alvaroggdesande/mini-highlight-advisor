# Landing Page (mini-spec)

A tiny, always-on page that sits **in front of** the Render app. Its only jobs:
sell in 3 seconds (before/after slider), send people into the app (one button), and
**hide the cold-start** by waking Render in the background while the visitor reads.

## Why not just a route in the React app?

Because the React app is served by Render, which **sleeps on the free tier**. A landing
route there would take 20–50s to load — the exact bad first impression we're avoiding.
So the landing page is a **standalone static file** hosted somewhere that never sleeps.

## Setup (5 minutes, no build)

1. Take two photos of the **same** primed mini: the raw photo, and the tool's painted
   preview. Save as `before.jpg` and `after.jpg` next to `landing.html`.
2. Open `landing.html`, set `APP_URL` (top of the `<script>`) to your Render URL.
3. Host the folder for free on any static host:
   - **GitHub Pages** — push to a repo, enable Pages. (You already use GitHub.)
   - or **Netlify / Cloudflare Pages** — drag-and-drop the folder.
4. That hosted URL is now the **one link you paste everywhere** (Reddit, Discord,
   emails) instead of the raw Render URL.

## How cold-start is hidden

On load, the page fires a background request to `APP_URL` to wake the Render container.
The visitor is reading/dragging the slider during those seconds, so by the time they
click **Try it free**, the app is warming or already warm. No blank-screen wait.

## What it deliberately is NOT

No framework, no analytics, no signup, no backend. One HTML file + two images. Add
things later (a GIF, testimonials, a tip-jar) by editing that one file — never touch
the app to change the pitch.

The file lives at `web-landing/landing.html`.
