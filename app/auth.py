"""Sign in with Google (OpenID Connect). Routes: /auth/google, /auth/callback, /logout."""

import os

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app import db

router = APIRouter()

oauth = OAuth()
oauth.register(
    name="google",
    # Google publishes its login URLs and signing keys here; Authlib reads them
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    client_kwargs={"scope": "openid email profile"},  # only ask for what we need
)


@router.get("/auth/google")
async def login_google(request: Request):
    """Step 1: send the browser to Google. Authlib adds a random `state` to the session."""
    redirect_uri = request.url_for("auth_callback")  # must match the URI registered at Google
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback")
async def auth_callback(request: Request):
    """Step 2: Google sends the browser back here with a one-time `code`."""
    try:
        # checks `state`, swaps code + client_secret for tokens, verifies the ID token signature
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse("/?error=login_failed", status_code=303)

    user = token.get("userinfo")  # the verified claims from the ID token
    if not user or not user.get("email_verified"):
        return RedirectResponse("/?error=login_failed", status_code=303)

    user_id = db.get_or_create_user(user["email"])

    request.session.clear()  # fresh session on login (prevents session fixation)
    request.session["user_id"] = user_id  # who you are, from now on
    request.session["email"] = user["email"]  # only for showing "Logged in as ..."
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
