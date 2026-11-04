"""One-time helper: obtain a Google Health API refresh token for the weight sync.

Run this locally once (and again only if the refresh token is ever revoked):

    GOOGLE_HEALTH_CLIENT_ID=... GOOGLE_HEALTH_CLIENT_SECRET=... \
        python scripts/google_health_authorize.py

It prints a consent URL. Open it, approve access, and you will land on
https://www.google.com with ?code=... in the address bar. Paste that code back
in here and the script prints the refresh token to store as the
GOOGLE_HEALTH_REFRESH_TOKEN repository secret.

Prerequisites (see https://developers.google.com/health/setup):
  * A Google Cloud project with the Google Health API enabled.
  * An OAuth client of type "Web application" whose authorized redirect URI is
    exactly https://www.google.com.
  * The OAuth consent screen published to "In production". Leaving it in
    "Testing" makes Google expire the refresh token after 7 days, which breaks
    an unattended scheduled sync. The app does not need to pass Google
    verification for personal use; you will just click through an
    "unverified app" warning once.
  * The Google account signed in to the Google Health mobile app (the
    rebranded Fitbit app) so the account is linked.
"""
import os
import sys
from urllib.parse import urlencode

import requests

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "https://www.google.com"
SCOPE = "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly"


def main():
    client_id = os.environ["GOOGLE_HEALTH_CLIENT_ID"]
    client_secret = os.environ["GOOGLE_HEALTH_CLIENT_SECRET"]

    url = AUTH_URL + "?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            # Both are needed to guarantee a refresh_token is returned.
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    print("\nOpen this URL in a browser and approve access:\n")
    print(url)
    print("\nAfter approving you will be redirected to https://www.google.com/?code=...")
    code = input("\nPaste the value of the code parameter: ").strip()

    resp = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    if not resp.ok:
        print(f"Token exchange failed {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    data = resp.json()
    if "refresh_token" not in data:
        print("No refresh_token in response; revoke the app at "
              "https://myaccount.google.com/permissions and run again.", file=sys.stderr)
        sys.exit(1)

    # Smoke test the token against the weight endpoint.
    check = requests.get(
        "https://health.googleapis.com/v4/users/me/dataTypes/weight/dataPoints",
        headers={"Authorization": f"Bearer {data['access_token']}"},
        params={"pageSize": 1},
    )
    print(f"\nTest call to weight endpoint: HTTP {check.status_code}")
    if not check.ok:
        print(check.text)

    print("\nStore this as the GOOGLE_HEALTH_REFRESH_TOKEN repository secret:\n")
    print(data["refresh_token"])
    if "refresh_token_expires_in" in data:
        days = int(data["refresh_token_expires_in"]) // 86400
        print(
            f"\nWARNING: this refresh token expires in ~{days} days, which means the "
            "OAuth consent screen is still in 'Testing'. Publish it to "
            "'In production' and run this script again."
        )


if __name__ == "__main__":
    main()
