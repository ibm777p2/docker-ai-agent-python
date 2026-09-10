from fastapi import FastAPI
import os

app = FastAPI()

MY_PROJECT = os.environ.get("MY_PROJECT") or "This is the project"
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise NotImplementedError("'API_KEY' was not set")

@app.get("/")

def read_index():
    return{"Nice": "Site again, nice", "project_name": MY_PROJECT, "API_KEY": API_KEY}