import os
import re
import subprocess
from functools import partial
from multiprocessing import Pool

from git import Repo, exc
from redis.client import Redis

from saku.core.config import SakuConfig
from saku.core.utils import chunk, un_chunk
from saku.db.connector import DbConnector
from saku.db.models import Document

SEARCHER_PATH = "/home/raz/go/bin/saku_regex"
GREPPER_PATH = "/usr/bin/pcregrep"
ESCAPE = r"\.*+?^${}()|[]"


def grep_match_detector(paths: list[str], regex: str, case_sensitive: bool):
    args = [
        "-I",  # Ignore binary files
        "-l",  # List matching files names
        "--buffer-size=1048576",  # 1 MB
    ]

    if not case_sensitive:
        args.append("-i")
    if "\n" in regex:
        args.append("-M")  # Multiline mode

    for char in ESCAPE:
        regex = regex.replace(char, f"\\{char}")

    p = subprocess.run([GREPPER_PATH, *args, regex, *paths], stdout=subprocess.PIPE)
    matching_files = [line for line in p.stdout.decode("utf-8").split("\n") if line]
    return matching_files


class QueryEngine:
    NGRAM_MATCHER = re.compile(r'"(.+?[^\\])"')

    def __init__(self, config: SakuConfig):
        self.config = config
        self.pool = Pool(12)
        self.db = DbConnector(config.DATABASE_URI)
        self.redis = Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

    @staticmethod
    def generate_ngrams(regex: str) -> list[str] | None:
        p = subprocess.run([SEARCHER_PATH, regex], stdout=subprocess.PIPE)
        encoded_ngrams = [l for l in p.stdout.split(b"\n") if l]

        ngram_strings = []
        for ngram in encoded_ngrams:
            ng = ngram.decode("unicode-escape")
            if ng.startswith("("):
                # Handle OR
                matches = QueryEngine.NGRAM_MATCHER.findall(ng)
                ngram_strings.append([f"ng:{ng}" for ng in matches])

            elif ng.startswith('"'):
                match = QueryEngine.NGRAM_MATCHER.match(ng)
                ngram_strings.append(f"ng:{match.group(1)}")
            elif ng == "+":
                # Match all
                return None

            else:
                # Case should not be encountered
                return None

        # ngram_strings = [ng.decode("unicode-escape") if ng]
        # ngrams = [f"ng:{g[1:4]}" for g in ngram_strings if g[1:4]]
        return ngram_strings

    def search(
        self,
        regex: str,
        case_sensitive: bool,
        skip: int = 0,
        limit: int = 20,
        size_lt: int | None = None,
        size_gt: int | None = None,
        path_like: str | None = None,
    ):
        ngrams = self.generate_ngrams(regex)

        session = self.db.get_session()
        query = session.query(Document)

        if size_gt is int and size_gt > 0:
            query = query.filter(Document.size >= size_gt)

        if size_lt is int and size_lt > 0:
            query = query.filter(Document.size <= size_lt)

        if path_like:
            query = query.filter(Document.path.regexp_match(path_like))

        if len(ngrams) > 1:
            serialized_doc_ids = self.redis.sinter(*ngrams)
            doc_ids = [int(x.decode()) for x in serialized_doc_ids]
            query = query.filter(Document.id.in_(doc_ids))

        query = query.order_by(Document.last_modified.desc())
        docs = list(query)

        possible_matches = [d.path for d in docs]
        possible_match_chunks = chunk(possible_matches, 100)

        match_detector = partial(grep_match_detector, regex=regex, case_sensitive=case_sensitive)
        matched_file_chunks = self.pool.map(match_detector, possible_match_chunks)
        matched_files = un_chunk(matched_file_chunks)
        matched_files = list(filter(lambda x: x is not None, matched_files))
        filtered_matches = matched_files[skip : skip + limit]

        matched_content = {
            self.get_git_url(path): open(path).read() for path in filtered_matches if self.get_git_url(path)
        }
        return {
            "total": len(matched_files),
            "skip": skip,
            "limit": min(limit, len(filtered_matches)),
            "matches": matched_content,
        }

    def get_git_url(self, path: str) -> str:
        dirs = next(os.walk(self.config.REPO_DIR))[1]
        for dir in dirs:
            repo_path = os.path.join(self.config.REPO_DIR, dir)
            try:
                _ = Repo(repo_path).git_dir
            except exc.InvalidGitRepositoryError:
                continue

            repo = Repo(repo_path)
            if path.startswith(repo_path):
                relative_path = path[len(repo_path) :]
                if relative_path.startswith("/.git"):
                    return None
                remote = repo.remotes.origin.url
                remote = remote.replace("git@github.com:", "https://github.com/")
                remote = remote.rstrip(".git")
                return f"{remote}/blob/master{relative_path}"
        return path


if __name__ == "__main__":
    # config = SakuConfig()
    # q = QueryEngine(config)
    # res = q.search("Arch", True)
    # print(res)
    print(QueryEngine.generate_ngrams("(raz)|(taz)test"))
