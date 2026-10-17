import sqlite3
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import db

MAX_NAME = 40
MAX_STATUS = 40

app = FastAPI()
db.init_db() # create the database and table if they don't exist yet

templates = Jinja2Templates(directory="app/templates")


# plain def (not async): sqlite3 is blocking, so FastAPI runs these in a thread
@app.get("/")
def read_family(request: Request, error: str | None = None):
    # each member as (id, name, [their statuses])
    family = [
        (member_id, name, db.list_member_statuses(member_id))
        for member_id, name in db.list_members()
    ]
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"family": family, "presets": db.list_statuses(), "error": error},
    )


@app.post("/members/{member_id}/statuses")
def give_status(member_id: int, status_id: Annotated[int, Form()]):
    try:
        db.add_status_to_member(member_id, status_id)
    except sqlite3.IntegrityError:  # already has it, or member/status doesn't exist
        pass
    return RedirectResponse("/", status_code=303)


@app.post("/members/{member_id}/statuses/custom")
def give_custom_status(member_id: int, text: Annotated[str, Form(max_length=MAX_STATUS)]):
    text = text.strip()
    if text:
        try:
            db.add_status_to_member(member_id, db.get_or_create_status(text))
        except sqlite3.IntegrityError:  # already has it, or member doesn't exist
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
        db.add_member(name)
    except sqlite3.IntegrityError:  # UNIQUE constraint on name
        return RedirectResponse("/?error=duplicate", status_code=303)
    return RedirectResponse("/", status_code=303)
