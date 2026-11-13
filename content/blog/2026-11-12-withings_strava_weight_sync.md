+++
date = 2026-11-12
description = "Same automation, new scale: syncing weight from the Withings API to Strava with GitHub Actions and Python."
series = ["cycling"]
tags = ["withings", "strava"]
title = "Withings to Strava Weight Sync"
hasMermaid = true
[paige]
edit = "https://github.com/pbj-writes/portfolio_hugo/edit/main/content/%s"
[paige.list_page]
disable_authors = false
disable_date = false
disable_keywords = false
disable_reading_time = false
disable_series = false
disable_summary = false
[paige.pages]
disable_authors = false
disable_date = false
disable_keywords = false
disable_next = true
disable_prev = true
disable_reading_time = false
disable_series = false
disable_toc = false
[paige.site]
disable_breadcrumbs = true
disable_credit = true
disable_license = true
+++

## Why Do This Again

So the Fitbit Aria 2 is retired and a Withings Body Comp has taken its spot. That means the Google Health version of the sync is no longer needed but still there if I'd ever like to resurrect it. Its [project page](/portfolio/strava-weight/) stays up with a notice, frozen at the last weight it synced on November 8, 2026. Withings runs its own developer program with a public API built for exactly this kind of thing, which made rebuilding the sync the easy part. You can see it running on the [Withings → Strava Sync project page](/portfolio/withings-strava-weight/).

The Strava half and the GitHub Actions half are nearly copy-paste from the previous project. The interesting part is that Withings does things differently.

## Withings Developer Setup

Three things to do before writing any code:

1. Create a developer account and an application in the [Withings Developer Dashboard](https://developer.withings.com/dashboard/). You get a client ID and client secret on creation.
2. Register a callback URL. Withings checks that the URL is a real, reachable HTTPS address, so `localhost` is out. Nothing actually needs to run there for a one-time personal authorization, so I used this website. After approving access, the authorization code just shows up in the address bar as `?code=...&state=...`.
3. Pick a scope. `user.metrics` covers weight and the rest of the body-composition measures.

The Withings+ paid subscription is not required because the Public Health Data API is free.


## The Python Script

Same shape as before: `requests` for the APIs, `PyNaCl` to encrypt secrets for the GitHub Secrets endpoint, about 150 lines.

```mermaid
---
config:
  theme: dark
---
flowchart LR
    A[Refresh Withings token] --> B[Save new Withings refresh token to GitHub Secrets]
    B --> C[getmeas: last 30 days of weight]
    C --> D[Decode value × 10^unit, pick newest]
    D --> E[Refresh Strava token]
    E --> F[Save new Strava refresh token]
    F --> G[Update Strava athlete weight]
    G --> H[Write data/withings_weight.json]
```

The `getmeas` call asks for `meastype=1` (weight, in kilograms) and `category=1` (real measurements, not goals) over a 30-day window, then takes the newest trusted group. Withings also supports a `lastupdate` parameter for incremental syncs and a webhook system that pushes new measurements to you, but webhooks need a server listening, and a scheduled GitHub Actions job isn't one. Polling twice a day is well under the one-request-per-ten-minutes guidance, so polling it is.

## GitHub Actions

The workflow is a near-duplicate of the Fitbit one. The Fitbit workflow is gone from the repo and this one replaces it; the old scripts stay in `scripts/` in case I ever want to resurrect them.

{{< paige-code lang="yaml" >}}
on:
  schedule:
    - cron: "0 16,21 * * *"
    - cron: "0 17,22 * * *"
  workflow_dispatch:
{{< /paige-code >}}

I only need two syncs a day, at 9 AM and 2 PM Pacific. GitHub cron only understands UTC, so the offset changes twice a year with daylight saving. I schedule both the winter and summer UTC times, and the first step of the job checks the Pacific hour and skips the run that is an hour off.

Secrets in the repository for this workflow:
- Withings client ID
- Withings client secret
- Withings refresh token (rotated every run)
- Strava client ID, client secret, and refresh token (carried over from the Fitbit sync)
- The same `WEIGHT_SYNC_PAT` that lets the script write secrets back

After the script finishes, the workflow commits `data/withings_weight.json`, which triggers the Hugo deploy. The project page reads that file at build time through the same shortcode as the old Fitbit page, just pointed at a different data file. The Fitbit page is still up, frozen at the last weight it ever synced.

## Done, Again

New scale, new API, same Strava profile, still zero manual steps. The Withings API asked for more reading up front than Fitbit ever did, but it also feels like it was designed for people to actually build on, which after this month is worth a lot.
