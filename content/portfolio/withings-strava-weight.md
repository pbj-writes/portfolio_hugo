+++
title = "Project: Withings → Strava Weight Sync"
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

## Current Strava Weight

{{< strava-weight source="withings_weight" >}}

## How It Works

A GitHub Actions workflow runs twice a day. A Python script refreshes OAuth tokens for both Withings and Strava, reads the latest weight measurement from the Withings Public Health Data API, decodes it, and writes it to the Strava athlete profile. Withings rotates its refresh token on every refresh, so the script writes the new Withings and Strava refresh tokens back to GitHub Secrets after each run and the integration never requires manual reauthentication.

This replaces the retired [Fitbit → Strava Weight Sync](/portfolio/strava-weight/) project. Same Strava side, same GitHub Actions pattern, different scale (Withings Body Comp) and a different API on the input side.

Read how I built this project in blog posts:
1. [Struggling with Zwift Weight](/blog/2024-01-07/struggling-with-zwift-weight/)
2. [Finish Weight Sync](/blog/2026-04-27/update-fitbit-to-strava-weight-sync/)
3. [Withings to Strava Weight Sync](/blog/2026-11-12/withings-to-strava-weight-sync/)

## Accounts and Hardware
- Withings account and developer application
- Withings Body Comp scale
- Strava account
