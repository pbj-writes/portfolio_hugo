+++
date = 2026-04-27
description = "Closing the loop on automated weight syncing with GitHub Actions and Python."
series = ["cycling"]
tags = ["fitbit", "strava"]
title = "Update: Fitbit to Strava Weight Sync"
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

## Where I Left Off

In my [previous post on this](/blog/2024-01-07/struggling-with-zwift-weight/), I had manually wired up the Fitbit and Strava APIs using Postman. I could pull my latest weight from Fitbit and push it to Strava. What I hadn't figured out yet was how to do it automatically, how to keep the OAuth tokens alive without babysitting them, and how to make it run on a schedule. That's all sorted now.

## Token Management

The blockers from before came down to one core problem: OAuth tokens expire. Strava access tokens die every six hours. Fitbit's also rotate. If I just stored a token somewhere and ran a script daily, it would stop working quickly.

The solution is [GitHub Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions) combined with refresh token rotation. I store six secrets in the repository: Fitbit client ID, Fitbit client secret, Fitbit refresh token, and the same three for Strava. Every time the automation runs, it uses the current refresh token to get a new access token, does its work, then writes the brand new refresh token back to GitHub Secrets. So the tokens are always current and the integration never goes stale.

Writing secrets back to GitHub requires a Personal Access Token (PAT) with `secrets:write` scope. That PAT lives as a seventh secret, `WEIGHT_SYNC_PAT`. One secret to keep all the others alive.

## The Python Script

The entire sync is handled by a single Python script using `requests` for API calls and `PyNaCl` for encrypting secrets before they're written to the GitHub API (a requirement of the GitHub Secrets endpoint).

At a high level it does five things in order:

1. Refreshes the Fitbit token and fetches the most recent weight log from the past seven days
2. Converts weight from lbs to kg (Strava stores weight in kg)
3. Refreshes the Strava token and updates the athlete profile weight
4. Rotates both new refresh tokens back to GitHub Secrets
5. Writes the weight and timestamp to `data/weight.json` for the website

The conversion is straightforward: lbs × 0.453592 = kg. If your Fitbit account is set to metric, you can flip a single env var in the workflow to skip the conversion.

## GitHub Actions

The workflow runs three times a day via a cron schedule and can also be triggered manually from the Actions tab.

{{< paige/code lang="yaml" >}}
on:
  schedule:
    - cron: "0 8,14,20 * * *"
  workflow_dispatch:
{{< /paige/code >}}

After the Python script completes, the workflow commits the updated `data/weight.json` and pushes it. That commit triggers the existing Hugo build workflow, which redeploys the site. The whole chain is automatic.

## The Website Page

Once `data/weight.json` is in the repo, Hugo's data templates can read it at build time. A custom shortcode reads the file and renders the current weight and last-synced timestamp as a static page — no client-side API calls, no tokens in the browser.

You can see it live at the [Fitbit → Strava Sync project page](/portfolio/strava-weight/).

## Done

The scale updates, Strava updates, the site reflects it. No manual steps. All of the infrastructure is free — GitHub Actions free tier, GitHub Pages for hosting, no third-party services involved. Just the Fitbit API, the Strava API, and about 100 lines of Python holding it all together.
