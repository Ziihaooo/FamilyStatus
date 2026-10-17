import sqlite3
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import db

MAX_NAME = 40

app = FastAPI()
db.init_db() # create the database and table if they don't exist yet

templates = Jinja2Templates(directory="app/templates")


# plain def (not async): sqlite3 is blocking, so FastAPI runs these in a thread
@app.get("/")
def read_family(request: Request, error: str | None = None):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"family": db.list_members(), "error": error},
    )


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
