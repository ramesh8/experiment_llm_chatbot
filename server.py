from vec_qa import VECQA

# query = input("Enter Query:")
# prompt = VECQA.getprompt(query)
# res = VECQA.get_openai_result(prompt)
# print(res)
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def index():
    return {"message":"Welcome"}


@app.get("/query")
async def query(request:Request, q=None):
    if q == None:
        return {"message":"Missing Query"}
    
    prompt = VECQA.getprompt(q)
    res = VECQA.get_openai_result(prompt)
    return {"question":q, "result":res}


@app.get("/askchat")
async def quickchat(request:Request):
    return templates.TemplateResponse(request=request, name="quickchat.html")

