import logging
import os
import time
from datetime import datetime
from multiprocessing.pool import ThreadPool
from pathlib import Path

import magic
from git import Repo
from redis.client import Redis

from saku.core.config import SakuConfig
from saku.core.encoding import byte_align_encode
from saku.core.utils import chunk, un_chunk
from saku.db.connector import DbConnector
from saku.db.models import Document, IndexNGram, create_db_and_tables
from saku.index.parser import DocumentParser

logging.basicConfig(level=logging.DEBUG)
LOG = logging

CHUNK_SIZE = 1000


class Indexer:
    def __init__(self, config: SakuConfig):
        self.config = config
        self.pool = ThreadPool(12)
        self.db = DbConnector(config.DATABASE_URI)
        self.parser = DocumentParser(config.MAX_SPARSE_GRAM_LENGTH)
        self.client = Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

        # Initialize Tables
        create_db_and_tables(self.db.engine)

    def index_directory(self, dir_path):
        with self.db.get_session() as session:
            results = session.query(Document).filter(Document.path.like(f"{dir_path}%"))
            tracked_files: dict[str, Document] = {f.path: f for f in results}

        files_present_in_path = set(
            str(pth.absolute()) for pth in Path(dir_path).rglob("*") if pth.is_file() and not pth.name.startswith(".")
        )
        LOG.debug(f"Found {len(files_present_in_path)} files in {dir_path}")
        tracked_file_paths = set(tracked_files.keys())

        newer_file_paths = files_present_in_path - tracked_file_paths
        deleted_file_paths = tracked_file_paths - files_present_in_path
        already_tracked_file_paths = tracked_file_paths - deleted_file_paths
        LOG.debug(f"Already Tracked {len(already_tracked_file_paths)} files")

        # Drop deleted files from index
        documents_to_delete = [tracked_files[pth] for pth in deleted_file_paths]
        self.drop_documents(documents_to_delete)

        # Track newer docs
        new_file_paths = list(newer_file_paths)
        LOG.debug(f"Tracking {len(new_file_paths)} newer files")
        newer_docs_to_index_chunks = self.pool.map(self.track_new_documents, chunk(new_file_paths, 2000))
        newer_docs_to_index = un_chunk(newer_docs_to_index_chunks)

        # Identify docs to re-index
        LOG.debug(f"Checking if {len(already_tracked_file_paths)} files need reindexing")
        already_tracked_docs = map(tracked_files.get, already_tracked_file_paths)
        modified_docs_chunks = self.pool.map(self.filter_consistent_docs, chunk(list(already_tracked_docs), 50))
        modified_docs = un_chunk(modified_docs_chunks)
        LOG.debug(f"{len(modified_docs)} need reindexing")

        # Index docs
        docs_to_index = newer_docs_to_index + modified_docs
        chunked = [docs_to_index[i : i + CHUNK_SIZE] for i in range(0, len(docs_to_index), CHUNK_SIZE)]
        parsed_ngram_chunks = self.pool.map(self.index_documents, chunked)

    def drop_documents(self, documents: list[Document]) -> None:
        session = self.db.get_session()
        deleted_document_ids = [d.id for d in documents]
        session.query(Document).filter(Document.id in deleted_document_ids).delete()
        session.commit()
        session.close()

    def track_new_documents(self, file_paths: list[str]):
        docs = []
        docs_not_indexed = 0
        doc_paths_indexed = []

        f_stats = map(os.stat, file_paths)
        for file_path, fstat in zip(file_paths, f_stats):
            file_size = fstat.st_size
            last_modified = datetime.fromtimestamp(fstat.st_mtime)

            if file_size > 1024 * 1024:
                docs_not_indexed += 1
                continue

            mime_type = magic.from_file(file_path, mime=True)
            if not mime_type.startswith("text"):
                docs_not_indexed += 1
                continue

            data = {"path": file_path, "size": file_size, "last_modified": last_modified, "mime_type": mime_type}
            doc_paths_indexed.append(file_path)
            docs.append(Document.parse_obj(data))

        LOG.debug(f"Skipping {docs_not_indexed} non text files")

        with self.db.get_session() as session:
            session.add_all(docs)
            session.commit()

            results = []
            # results = session.query(Document).filter(Document.path.in_(doc_paths_indexed)).all()
            session.close()

        return results

    def filter_consistent_docs(self, documents: list[Document]) -> list[Document]:
        session = self.db.get_session()

        docs_to_reindex = []
        for doc in documents:
            fstat = os.stat(doc.path)
            file_size = fstat.st_size
            last_modified = datetime.fromtimestamp(fstat.st_mtime)

            if (
                doc.size != fstat.st_size  # Size mismatch
                or doc.last_modified != last_modified  # Some content change
                or (doc.last_indexed is None and doc.mime_type.startswith("text"))  # Not indexed
                or (doc.last_indexed is not None and doc.last_indexed < last_modified)  # Modified after indexing
            ):
                mime_type = magic.from_file(doc.path, mime=True)
                updates = {"size": file_size, "last_modified": last_modified, "mime_type": mime_type}
                session.query(Document).filter(Document.id == doc.id).update(updates)

                if mime_type.startswith("text"):
                    # Re-index only text files
                    docs_to_reindex.append(doc)

        session.commit()
        session.close()
        return docs_to_reindex

    def index_documents(self, documents: list[Document]) -> set[str]:
        parsed_ngrams = {}

        start_time = time.time()
        for doc in documents:
            LOG.debug(f"Indexing Document: {doc.path}")
            current_grams = self.parser.parse_document(doc.path)
            doc.last_indexed = datetime.now()

            for grm in current_grams:
                parsed_ngrams.setdefault(grm, []).append(doc.id)
        LOG.debug(f"Indexed: {time.time() - start_time}")

        pipe = self.client.pipeline()
        for ngram, postings in parsed_ngrams.items():
            pipe.sadd(f"ng:{ngram}", *postings)
        pipe.execute()
        LOG.debug(f"Redis Save: {time.time() - start_time}")

        # Save to DB
        session = self.db.get_session()
        # known_ngrams = set(parsed_ngrams.keys())
        # index_grams = session.query(IndexNGram.ngram).filter(IndexNGram.ngram.in_(known_ngrams)).all()
        # new_ngrams = known_ngrams - set(g.ngram for g in index_grams)
        # print("DB read: ", time.time() - start_time)
        #
        # new_index_grams = []
        # for ngram, posting_list in zip(new_ngrams, map(parsed_ngrams.get, new_ngrams)):
        #     encoded_doc_ids = b"".join(byte_align_encode(posting) for posting in posting_list)
        #     index_gram = IndexNGram(ngram=ngram, doc_ids=encoded_doc_ids)
        #     new_index_grams.append(index_gram)
        #
        # session.add_all(new_index_grams)
        session.add_all(documents)
        session.commit()
        session.close()
        LOG.debug(f"DB Save: {time.time() - start_time}")
        return set(parsed_ngrams.keys())


if __name__ == "__main__":
    overall_start = time.time()
    indexer = Indexer(SakuConfig())
    indexer.index_directory("/home/raz/Temp/repos")
    LOG.debug(f"Total Time Taken : {time.time() - overall_start}")
