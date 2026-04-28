import base64
import json
import os
import requests
from datetime import datetime, timezone
from nacl import encoding, public


# Set to 'lbs' if your Fitbit profile unit is pounds, 'kg' if metric.
FITBIT_UNIT = os.environ.get("FITBIT_UNIT", "lbs")


def refresh_fitbit_token():
    client_id = os.environ["FITBIT_CLIENT_ID"]
    client_secret = os.environ["FITBIT_CLIENT_SECRET"]
    refresh_token = os.environ["FITBIT_REFRESH_TOKEN"]
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        "https://api.fitbit.com/oauth2/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )
    if not resp.ok:
        raise RuntimeError(f"Fitbit token refresh failed {resp.status_code}: {resp.text}")
    data = resp.json()
    return data["access_token"], data["refresh_token"]


def get_fitbit_weight(access_token):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resp = requests.get(
        f"https://api.fitbit.com/1/user/-/body/log/weight/date/{today}/7d.json",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    logs = resp.json().get("weight", [])
    if not logs:
        raise ValueError("No weight logged in the past 7 days")
    return logs[-1]["weight"]


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


def lbs_to_kg(lbs):
    return round(lbs * 0.453592, 1)


def main():
    gh_token = os.environ["GH_PAT"]
    repo = os.environ["GH_REPO"]

    print("Refreshing Fitbit token...")
    fitbit_access, fitbit_refresh_new = refresh_fitbit_token()

    # Save immediately so a failure later doesn't burn this token
    print("Saving new Fitbit refresh token...")
    key_data = _get_repo_public_key(gh_token, repo)
    update_github_secret("FITBIT_REFRESH_TOKEN", fitbit_refresh_new, gh_token, repo, key_data)

    print("Fetching Fitbit weight...")
    weight_raw = get_fitbit_weight(fitbit_access)
    weight_lbs = round(weight_raw, 1) if FITBIT_UNIT == "lbs" else round(weight_raw * 2.20462, 1)
    weight_kg = lbs_to_kg(weight_lbs)
    print(f"Weight: {weight_lbs} lbs / {weight_kg} kg")

    print("Refreshing Strava token...")
    strava_access, strava_refresh_new = refresh_strava_token()

    # Save immediately for the same reason
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
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
            indent=2,
        )

    print("Done.")


if __name__ == "__main__":
    main()
