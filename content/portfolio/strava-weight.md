+++
title = "Project: Fitbit → Strava Weight Sync"
[paige.pages]
disable_authors = true
disable_date = true
disable_keywords = true
disable_next = true
disable_prev = true
disable_reading_time = true
disable_series = true
disable_toc = true
+++

## Final Synced Weight

{{< strava-weight >}}

> **This project is retired and no longer syncs.** It last worked on November 8, 2026, the day I replaced the scale. The value above is the final weight it ever pushed to Strava. Its successor is the [Withings → Strava Weight Sync](/portfolio/withings-strava-weight/).

## How It Worked

A GitHub Actions workflow ran three times daily. A Python script refreshed OAuth tokens for both Fitbit and Strava, read the latest weight from the Fitbit API, converted it, and wrote it to the Strava athlete profile. Refresh tokens were automatically rotated back into GitHub Secrets after each run so the integration never required manual reauthentication. When the Fitbit API was retired, the script briefly moved to the Google Health API before the scale itself was replaced.

Read how I progressed this project in blog posts:
1. [Struggling with Zwift Weight](/blog/2024-01-07/struggling-with-zwift-weight/)  
2. [Finish Weight Sync](/blog/2026-04-27/update-fitbit-to-strava-weight-sync/)
3. [Withings to Strava Weight Sync](/blog/2026-11-12/withings-to-strava-weight-sync/) (why it was retired)

## Accounts and Hardware
- Fitbit account
- Fitbit Aria 2 scale (retired)
- Strava account
