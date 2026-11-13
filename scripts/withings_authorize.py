"""One-time helper: obtain a Withings refresh token for the weight sync.

Run this locally once (and again only if the refresh token is ever revoked or
left unused for a year):

    python scripts/withings_authorize.py

It prompts for the client ID and client secret (the secret is not echoed). To
skip the prompts, set WITHINGS_CLIENT_ID and WITHINGS_CLIENT_SECRET instead.

It prints a consent URL. Open it, approve access, and you will land on the
callback URL registered for the app with ?code=...&state=... in the address
bar. Copy that whole URL and paste it back in here *quickly*: Withings
authorization codes expire 30 seconds after they are issued. The script exchanges the code and
prints the refresh token to store as the WITHINGS_REFRESH_TOKEN repository
secret.

Prerequisites (see https://developer.withings.com/developer-guide/v3/
integration-guide/public-health-data-api/developer-account/
create-your-accesses-no-medical-cloud):
  * A Withings developer account and an application created in the
    Developer Dashboard at https://developer.withings.com/dashboard/.
    The Public Health Data API is free; a Withings+ consumer subscription is
    not required.
  * The application's callback URL must be a real, publicly reachable HTTPS
    URL (the dashboard has a "test reachability" button; localhost is not
    accepted). This site works fine: https://pbjwrites.info/ . Nothing has
    to run there; the authorization code just shows up in the address bar.
    Override with WITHINGS_REDIRECT_URI if the registered URL differs.
  * The Withings account must own the scale whose weight you want to sync.

Pass --demo to authorize against Withings' demo user (mode=demo), which
returns fake measurements without a real device. Useful for checking the
wiring before the scale arrives.
"""
import getpass
import os
import secrets
import sys
import time
from urllib.parse import parse_qs, urlencode, urlparse

import requests

AUTHORIZE_URL = "https://account.withings.com/oauth2_user/authorize2"
TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
MEASURE_URL = "https://wbsapi.withings.net/measure"
DEFAULT_REDIRECT_URI = "https://pbjwrites.info/"
# user.metrics covers weight and the other body-composition measures.
SCOPE = "user.metrics"


def get_credential(env_name, label, secret=False):
    """Read a credential from the environment, or prompt for it. Never accept
    an empty value: an empty client_id produces a consent URL that Withings
    rejects with "Missing client_id"."""
    value = os.environ.get(env_name, "").strip()
    if not value:
        prompt = f"{label}: "
        value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
    if not value:
        print(f"{label} is empty; cannot continue.", file=sys.stderr)
        sys.exit(1)
    return value


def main():
    client_id = get_credential("WITHINGS_CLIENT_ID", "Withings client ID")
    client_secret = get_credential("WITHINGS_CLIENT_SECRET", "Withings client secret", secret=True)
    # Show enough of each value to compare against the dashboard without
    # echoing the whole secret. A wrong secret only surfaces at the very end
    # of the flow as status 503 "invalid client id/secret".
    print(f"\nClient ID:     {client_id}")
    print(f"Client secret: {client_secret[:4]}...{client_secret[-4:]} ({len(client_secret)} characters)")
    if client_id == client_secret:
        print("Client ID and secret are identical; you probably pasted the ID twice.", file=sys.stderr)
        sys.exit(1)
    if input("Do these match the app in the Withings Developer Dashboard? [Y/n] ").strip().lower() in ("n", "no"):
        sys.exit(1)
    redirect_uri = os.environ.get("WITHINGS_REDIRECT_URI", DEFAULT_REDIRECT_URI)
    demo = "--demo" in sys.argv

    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": SCOPE,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if demo:
        params["mode"] = "demo"

    print("\nOpen this URL in a browser and approve access:\n")
    print(AUTHORIZE_URL + "?" + urlencode(params))
    print(f"\nAfter approving you will be redirected to {redirect_uri}?code=...&state=...")
    print("The code is only valid for 30 seconds from the moment you land on that page,")
    print("so copy the ENTIRE URL from the address bar and paste it here in one go.")
    pasted = input("\nPaste the full redirect URL: ").strip()
    started = time.monotonic()
    if "code=" in pasted:
        query = parse_qs(urlparse(pasted).query)
        code = query.get("code", [""])[0]
        returned_state = query.get("state", [""])[0]
    else:
        # Fall back to a bare code; skip the state check in that case.
        code, returned_state = pasted, state
    if not code:
        print("No code found in what you pasted.", file=sys.stderr)
        sys.exit(1)
    if returned_state != state:
        print(f"state mismatch (got {returned_state!r}); start over.", file=sys.stderr)
        sys.exit(1)

    resp = requests.post(
        TOKEN_URL,
        data={
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    payload = resp.json() if resp.ok else {}
    # Withings answers HTTP 200 for almost everything; the real result is in
    # the "status" field (0 = success).
    if not resp.ok or payload.get("status") != 0:
        print(f"Token exchange failed HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        if payload.get("status") == 304 or "invalid code" in payload.get("error", ""):
            print("The authorization code was rejected; it only lives 30 seconds and "
                  f"the exchange was sent {time.monotonic() - started:.1f}s after you "
                  "pasted. Have this terminal ready, approve in the browser, copy the "
                  "whole URL, paste, Enter. Each attempt needs a fresh consent URL, "
                  "so run the script again.", file=sys.stderr)
        if payload.get("status") == 503 and "client" in payload.get("error", ""):
            print("status 503 'invalid client id/secret' = the client secret does not "
                  "match this client ID. The consent screen only validates the ID, so "
                  "re-copy the secret from the Developer Dashboard (reveal it first, "
                  "then copy the whole value) and run again.", file=sys.stderr)
        sys.exit(1)
    body = payload["body"]

    # Smoke test the token against the weight endpoint.
    check = requests.post(
        MEASURE_URL,
        headers={"Authorization": f"Bearer {body['access_token']}"},
        data={"action": "getmeas", "meastype": 1, "category": 1},
    )
    check_payload = check.json() if check.ok else {}
    groups = check_payload.get("body", {}).get("measuregrps", [])
    print(f"\nTest call to getmeas: HTTP {check.status_code}, "
          f"status {check_payload.get('status')}, {len(groups)} weight group(s) found")
    if check_payload.get("status") != 0:
        print(check.text)

    print(f"\nWithings user id: {body['userid']}")
    print(f"Granted scope:    {body['scope']}")
    print("\nStore this as the WITHINGS_REFRESH_TOKEN repository secret:\n")
    print(body["refresh_token"])
    print("\nNote: Withings rotates refresh tokens on every refresh, so the sync "
          "script writes the newest one back to GitHub Secrets after each run.")


if __name__ == "__main__":
    main()
