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

## Current Strava Weight

{{< strava-weight >}}

## How It Works

A GitHub Actions workflow runs three times daily. A Python script refreshes OAuth tokens for both Fitbit and Strava, reads the latest weight from the Fitbit API, converts it, and writes it to the Strava athlete profile. Refresh tokens are automatically rotated back into GitHub Secrets after each run so the integration never requires manual reauthentication.

Read the full write-up in the [blog post](/blog/2026-04-27/finishing-the-fitbit-to-strava-weight-sync/).
