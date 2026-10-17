from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()

templates = Jinja2Templates(directory="app/templates")

@app.get("/")
async def read_member(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"family": family}
    )

family= ["Dad","Mom","Big Sis","Sinyi Sis","A girl","A be","King"]

