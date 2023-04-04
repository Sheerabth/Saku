import requests

HOST = "http://localhost:8000"


def search_request(
    regex: str,
    skip: int = 0,
    limit: int = 20,
    case_sensitive: bool = True,
    size_lt: int | None = None,
    size_gt: int | None = None,
    path_like: str | None = None,
):
    params = {
        "skip": skip,
        "limit": limit,
        "size_lt": size_lt,
        "size_gt": size_gt,
        "path_like": path_like,
        "case_sensitive": case_sensitive,
    }
    resp = requests.post(f"{HOST}/search", json={"regex": regex}, params=params)
    return resp.json()


def clone_request(url: str):
    params = {"url": url}
    resp = requests.post(f"{HOST}/repo", params=params)
    return resp.json()


def index_request():
    resp = requests.put(f"{HOST}/repo/index")
    return resp.json()
