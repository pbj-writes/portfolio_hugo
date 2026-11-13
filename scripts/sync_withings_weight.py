import base64
import json
import os
import time
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from nacl import encoding, public


# Withings Public Health Data API. Every call is a POST with an "action"
# form parameter, and the API answers HTTP 200 for nearly everything: the real
# outcome is the "status" field in the JSON body (0 = success).
# See https://developer.withings.com/api-reference/
WITHINGS_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
WITHINGS_MEASURE_URL = "https://wbsapi.withings.net/measure"
MEASTYPE_WEIGHT = 1  # kg
CATEGORY_REAL = 1  # 1 = real measurements, 2 = user objectives
# attrib values that mean "captured by a device and definitely this user" or
# "entered manually by this user". We skip 1 (ambiguous: the scale could not
# tell which household member stepped on) and 4 (placeholder entered at
# account creation).
TRUSTED_ATTRIBS = {0, 2, 5, 7, 8}
LOCAL_TZ = ZoneInfo("America/Los_Angeles")

WITHINGS_STATUS_HINTS = {
    100: "no data found",
    304: "authorization code missing or expired",
    305: "missing required parameter",
    342: "OAuth credentials missing or incorrect (check WITHINGS_CLIENT_ID/SECRET)",
    343: "access token missing or invalid",
    401: "refresh token invalid or already rotated: re-run scripts/withings_authorize.py "
         "and update WITHINGS_REFRESH_TOKEN",
    601: "rate limit exceeded (Withings allows roughly one poll per 10 minutes per user)",
}


def withings_post(url, data, access_token=None):
    """POST to a Withings endpoint and return the response body on success."""
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    resp = requests.post(url, data=data, headers=headers)
    resp.raise_for_status()
    payload = resp.json()
    status = payload.get("status")
    if status != 0:
        hint = WITHINGS_STATUS_HINTS.get(status, "")
        raise RuntimeError(
            f"Withings {data.get('action')} failed with status {status}"
            f"{' (' + hint + ')' if hint else ''}: {payload.get('error', resp.text)}"
        )
    return payload["body"]


def refresh_withings_token():
    """Exchange the current refresh token for a new access token.

    Withings rotates refresh tokens: every refresh returns a new one, and the
    old one stops working 8 hours later or as soon as the new access token is
    used. The caller must persist the returned refresh token immediately.
    """
    body = withings_post(
        WITHINGS_TOKEN_URL,
        {
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": os.environ["WITHINGS_CLIENT_ID"],
            "client_secret": os.environ["WITHINGS_CLIENT_SECRET"],
            "refresh_token": os.environ["WITHINGS_REFRESH_TOKEN"],
        },
    )
    return body["access_token"], body["refresh_token"]


def get_withings_weight(access_token):
    """Return (weight_kg, logged_at) for the most recent weight measurement in
    the past 30 days, or None if there are none."""
    now = int(time.time())
    data = {
        "action": "getmeas",
        "meastype": MEASTYPE_WEIGHT,
        "category": CATEGORY_REAL,
        "startdate": now - 30 * 86400,
        "enddate": now,
    }
    groups = []
    while True:
        body = withings_post(WITHINGS_MEASURE_URL, data, access_token)
        groups.extend(body.get("measuregrps", []))
        if not body.get("more"):
            break
        data["offset"] = body["offset"]

    candidates = []
    for grp in groups:
        if grp.get("attrib") not in TRUSTED_ATTRIBS:
            print(f"Skipping measure group {grp.get('grpid')} with attrib={grp.get('attrib')}")
            continue
        for m in grp.get("measures", []):
            if m.get("type") == MEASTYPE_WEIGHT:
                candidates.append((grp["date"], m))

    if not candidates:
        return None

    date, measure = max(candidates, key=lambda c: c[0])
    # Withings stores every measure as an integer mantissa plus a power-of-ten
    # exponent, e.g. value=84300, unit=-3 -> 84.3 kg.
    weight_kg = round(measure["value"] * (10 ** measure["unit"]), 1)
    logged_at = datetime.fromtimestamp(date, tz=LOCAL_TZ)
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

    print("Refreshing Withings token...")
    withings_access, withings_refresh_new = refresh_withings_token()

    # Save before doing anything else: the old refresh token dies as soon as
    # the new access token is used, so a failure later must not strand us.
    print("Saving new Withings refresh token...")
    update_github_secret(
        "WITHINGS_REFRESH_TOKEN", withings_refresh_new, gh_token, repo, key_data
    )

    print("Fetching weight from Withings...")
    result = get_withings_weight(withings_access)
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

    print("Writing data/withings_weight.json...")
    os.makedirs("data", exist_ok=True)
    with open("data/withings_weight.json", "w") as f:
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
