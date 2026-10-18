import os
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import auth, db

MAX_NAME = 40
MAX_STATUS = 40
FAMILY_TZ = timezone(timedelta(hours=8))  # family's local time, used for "today"
DURATIONS = ["1h", "3h", "today", "forever"]
FAMILY_ID = 1  # TEMPORARY: everyone is in family 1 until login tells us whose family it is


def utc_now():
    return datetime.now(UTC)


def expiry_for(duration):
    """When a status set now should expire, as a UTC string. None = until changed."""
    if duration not in DURATIONS:
        raise HTTPException(status_code=422, detail="Invalid duration")
    now = utc_now()
    if duration == "1h":
        until = now + timedelta(hours=1)
    elif duration == "3h":
        until = now + timedelta(hours=3)
    elif duration == "today":  # midnight tonight, family time
        local = now.astimezone(FAMILY_TZ)
        until = local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    else:
        return None
    return until.astimezone(UTC).isoformat()

app = FastAPI()
db.init_db() # create the database and table if they don't exist yet

# Signed session cookie. No SESSION_SECRET (e.g. in tests) → a random one per start,
# never a hardcoded fallback that could end up in production.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32),
    same_site="lax",
    https_only=False,  # TODO(OPS): True once served over HTTPS
)
app.include_router(auth.router)

templates = Jinja2Templates(directory="app/templates")


# plain def (not async): sqlite3 is blocking, so FastAPI runs these in a thread
@app.get("/")
def read_family(request: Request, error: str | None = None):
    # each member as (id, name, [their statuses])
    now = utc_now().isoformat()
    family = [
        (member_id, name, db.list_member_statuses(member_id, now))
        for member_id, name in db.list_members(FAMILY_ID)
    ]
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "family": family,
            "presets": db.list_statuses(),
            "error": error,
            "email": request.session.get("email"),  # None if not logged in
        },
    )


@app.post("/members/{member_id}/statuses")
def give_status(
    member_id: int,
    status_id: Annotated[int, Form()],
    duration: Annotated[str, Form()] = "forever",
):
    until = expiry_for(duration)
    try:
        db.add_status_to_member(member_id, status_id, until)
    except sqlite3.IntegrityError:  # member or status doesn't exist
        pass
    return RedirectResponse("/", status_code=303)


@app.post("/members/{member_id}/statuses/custom")
def give_custom_status(
    member_id: int,
    text: Annotated[str, Form(max_length=MAX_STATUS)],
    duration: Annotated[str, Form()] = "forever",
):
    until = expiry_for(duration)
    text = text.strip()
    if text:
        try:
            db.add_status_to_member(member_id, db.get_or_create_status(text), until)
        except sqlite3.IntegrityError:  # member doesn't exist
            pass
    return RedirectResponse("/", status_code=303)


@app.post("/members/{member_id}/statuses/{status_id}/remove")
def take_status(member_id: int, status_id: int):
    db.remove_status_from_member(member_id, status_id)
    return RedirectResponse("/", status_code=303)


@app.post("/members")
def create_member(name: Annotated[str, Form(max_length=MAX_NAME)]):
    name = name.strip()
    if not name:
        return RedirectResponse("/?error=empty", status_code=303)
    try:
        db.add_member(FAMILY_ID, name)
    except sqlite3.IntegrityError:  # UNIQUE (family_id, name)
        return RedirectResponse("/?error=duplicate", status_code=303)
    return RedirectResponse("/", status_code=303)
