import base64
import json
import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from nacl import encoding, public


# Google turned off the legacy Fitbit Web API and Fitbit OAuth endpoints on
# 2026-11-02 (they now return HTTP 410 Gone). Weight is read from its
# replacement, the Google Health API, which uses standard Google OAuth 2.0.
# See https://developers.google.com/health/migration
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_HEALTH_API = "https://health.googleapis.com/v4"
LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def refresh_google_token():
    """Exchange the long-lived Google refresh token for an access token.

    Google does not rotate refresh tokens on refresh, so unlike the old Fitbit
    flow there is normally nothing to write back. If Google ever does return a
    new refresh_token we hand it to the caller so it can be saved.
    """
    resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": os.environ["GOOGLE_HEALTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_HEALTH_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_HEALTH_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
    )
    if not resp.ok:
        hint = ""
        if "invalid_grant" in resp.text:
            hint = (
                " (invalid_grant usually means the refresh token expired: a Google "
                "OAuth consent screen left in 'Testing' status issues refresh tokens "
                "that expire after 7 days. Publish the consent screen to "
                "'In production' and re-run scripts/google_health_authorize.py.)"
            )
        raise RuntimeError(f"Google token refresh failed {resp.status_code}: {resp.text}{hint}")
    data = resp.json()
    return data["access_token"], data.get("refresh_token")


def get_google_health_weight(access_token):
    """Return (weight_kg, logged_at) for the most recent weight sample in the
    past 30 days, or None if there are no samples."""
    since = (datetime.now(LOCAL_TZ) - timedelta(days=30)).strftime("%Y-%m-%d")
    points = []
    params = {"filter": f'weight.sample_time.civil_time >= "{since}"'}
    while True:
        resp = requests.get(
            f"{GOOGLE_HEALTH_API}/users/me/dataTypes/weight/dataPoints",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        if resp.status_code == 400 and "ACCOUNT_NOT_LINKED" in resp.text:
            raise RuntimeError(
                "Google Health account not linked: sign in to the Google Health "
                "mobile app with this Google account, then re-authorize. "
                f"Response: {resp.text}"
            )
        resp.raise_for_status()
        body = resp.json()
        points.extend(p for p in body.get("dataPoints", []) if "weight" in p)
        token = body.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token

    if not points:
        return None

    def sample_time(p):
        return datetime.fromisoformat(
            p["weight"]["sampleTime"]["physicalTime"].replace("Z", "+00:00")
        )

    latest = max(points, key=sample_time)
    weight_kg = round(latest["weight"]["weightGrams"] / 1000, 1)
    logged_at = sample_time(latest).astimezone(LOCAL_TZ)
    return weight_kg, logged_at


def refresh_strava_token():
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": os.environ["STRAVA_CLIENT_ID"],
            "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
            "refresh_token": os.environ["STRAVA_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data["refresh_token"]


def update_strava_weight(access_token, weight_kg):
    resp = requests.put(
        "https://www.strava.com/api/v3/athlete",
        headers={"Authorization": f"Bearer {access_token}"},
        data={"weight": weight_kg},
    )
    resp.raise_for_status()


def _get_repo_public_key(gh_token, repo):
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
        },
    )
    resp.raise_for_status()
    return resp.json()


def update_github_secret(secret_name, secret_value, gh_token, repo, key_data):
    pub_key = public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder())
    encrypted = base64.b64encode(
        public.SealedBox(pub_key).encrypt(secret_value.encode())
    ).decode()
    resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
        },
        json={"encrypted_value": encrypted, "key_id": key_data["key_id"]},
    )
    resp.raise_for_status()


def kg_to_lbs(kg):
    return round(kg * 2.20462, 1)


def main():
    gh_token = os.environ["GH_PAT"]
    repo = os.environ["GH_REPO"]
    key_data = _get_repo_public_key(gh_token, repo)

    print("Refreshing Google Health token...")
    google_access, google_refresh_new = refresh_google_token()
    if google_refresh_new:
        print("Google returned a new refresh token; saving it...")
        update_github_secret(
            "GOOGLE_HEALTH_REFRESH_TOKEN", google_refresh_new, gh_token, repo, key_data
        )

    print("Fetching weight from Google Health...")
    result = get_google_health_weight(google_access)
    if result is None:
        print("No weight logged in the past 30 days — skipping.")
        return
    weight_kg, logged_at = result
    weight_lbs = kg_to_lbs(weight_kg)
    print(f"Weight: {weight_lbs} lbs / {weight_kg} kg (logged {logged_at.isoformat()})")

    print("Refreshing Strava token...")
    strava_access, strava_refresh_new = refresh_strava_token()

    # Save immediately so a failure later doesn't burn this token
    print("Saving new Strava refresh token...")
    update_github_secret("STRAVA_REFRESH_TOKEN", strava_refresh_new, gh_token, repo, key_data)

    print("Updating Strava athlete weight...")
    update_strava_weight(strava_access, weight_kg)

    print("Writing data/weight.json...")
    os.makedirs("data", exist_ok=True)
    with open("data/weight.json", "w") as f:
        json.dump(
            {
                "weight_lbs": weight_lbs,
                "weight_kg": weight_kg,
                "updated_at": logged_at.isoformat(),
            },
            f,
            indent=2,
        )

    print("Done.")


if __name__ == "__main__":
    main()
