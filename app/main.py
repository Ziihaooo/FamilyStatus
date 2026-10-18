import os
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import auth, db

MAX_NAME = 40
MAX_STATUS = 40
FAMILY_TZ = timezone(timedelta(hours=8))  # family's local time, used for "today"
DURATIONS = ["1h", "3h", "today", "forever"]


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


def current_user_id(request: Request):
    """Who is logged in (from the signed session cookie), or None."""
    return request.session.get("user_id")


def current_family_id(request: Request):
    """The family this user is looking at right now, or None if they have no family.

    session["family_id"] remembers the choice; it is re-checked on every request,
    so a stale or tampered value can never show someone else's family.
    """
    user_id = current_user_id(request)
    if user_id is None:
        return None
    family_id = request.session.get("family_id")
    if family_id is not None and db.is_member_of(user_id, family_id):
        return family_id
    families = db.list_families_for_user(user_id)
    if not families:
        return None
    request.session["family_id"] = families[0][0]  # default: their first family
    return families[0][0]


UserId = Annotated[int | None, Depends(current_user_id)]
FamilyId = Annotated[int | None, Depends(current_family_id)]


def check_member_access(member_id: int, family_id: FamilyId):
    """Gate for every route that touches a member: must be logged in, and the
    member must be in YOUR current family. 404 (not 403) so attackers can't tell
    'exists in another family' from 'doesn't exist'."""
    if family_id is None or not db.member_in_family(member_id, family_id):
        raise HTTPException(status_code=404, detail="Member not found")
    return member_id


MemberId = Annotated[int, Depends(check_member_access)]


# plain def (not async): sqlite3 is blocking, so FastAPI runs these in a thread
@app.get("/welcome")
def welcome(request: Request, user_id: UserId):
    if user_id is None:
        return RedirectResponse("/", status_code=303)  # not logged in
    return templates.TemplateResponse(
        request=request, name="welcome.html", context={"email": request.session.get("email")}
    )


@app.get("/")
def read_family(
    request: Request, user_id: UserId, family_id: FamilyId, error: str | None = None
):
    if user_id is None:  # logged out: show only the sign-in link, no family data
        return templates.TemplateResponse(request=request, name="index.html", context={})
    if family_id is None:
        return RedirectResponse("/welcome", status_code=303)  # logged in, but no family yet

    # each member as (id, name, [their statuses])
    now = utc_now().isoformat()
    family = [
        (member_id, name, db.list_member_statuses(member_id, now))
        for member_id, name in db.list_members(family_id)
    ]
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "logged_in": True,
            "family": family,
            "presets": db.list_statuses(),
            "error": error,
            "email": request.session.get("email"),  # None if not logged in
        },
    )


@app.post("/members/{member_id}/statuses")
def give_status(
    member_id: MemberId,
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
    member_id: MemberId,
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
def take_status(member_id: MemberId, status_id: int):
    db.remove_status_from_member(member_id, status_id)
    return RedirectResponse("/", status_code=303)


@app.post("/families")
def create_family(
    request: Request,
    user_id: UserId,  # who you are comes from the session, never the form
    family_name: Annotated[str, Form(max_length=MAX_NAME)],
    your_name: Annotated[str, Form(max_length=MAX_NAME)],
):
    if user_id is None:
        return RedirectResponse("/", status_code=303)
    family_name, your_name = family_name.strip(), your_name.strip()
    if not family_name or not your_name:
        return RedirectResponse("/welcome", status_code=303)
    try:
        new_family_id = db.create_family(family_name, user_id, your_name)
    except db.DuplicateFamilyName:
        return RedirectResponse("/welcome", status_code=303)
    request.session["family_id"] = new_family_id  # switch to the family you just made
    return RedirectResponse("/", status_code=303)


@app.post("/members")
def create_member(family_id: FamilyId, name: Annotated[str, Form(max_length=MAX_NAME)]):
    if family_id is None:
        return RedirectResponse("/", status_code=303)
    name = name.strip()
    if not name:
        return RedirectResponse("/?error=empty", status_code=303)
    try:
        db.add_member(family_id, name)
    except sqlite3.IntegrityError:  # UNIQUE (family_id, name)
        return RedirectResponse("/?error=duplicate", status_code=303)
    return RedirectResponse("/", status_code=303)
