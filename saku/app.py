import os
import subprocess
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from git import GitCommandError, Repo
from pydantic import HttpUrl

from saku.core.config import SakuConfig
from saku.index.query import QueryEngine

app = FastAPI()
config = SakuConfig()
query_engine = QueryEngine(config)


@app.post("/repo")
def clone(url: HttpUrl):
    try:
        Repo.clone_from(url, os.path.join(config.REPO_DIR, Path(url).stem))
        return {"message": f"`{url} clone successfully`"}
    except GitCommandError:
        raise HTTPException(400, "Repo already exists")


@app.put("/repo/index")
def index():
    subprocess.run(["./venv/bin/python", "./saku/index/indexer.py"])
    subprocess.run(["./venv/bin/python", "./saku/index/indexer.py"])
    return {"message": "Indexing completed"}


@app.post("/search")
def search(
    regex: bytes = Body(..., embed=True),
    skip: int = 0,
    limit: int = 20,
    case_sensitive: bool = True,
    size_lt: int | None = None,
    size_gt: int | None = None,
    path_like: str | None = None,
):
    regex_str = regex.decode("utf-8")
    return query_engine.search(regex_str, case_sensitive, skip, limit, size_lt, size_gt, path_like)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
