from pathlib import Path

import magic
from sqlmodel import Session, create_engine

from saku.core.config import SakuConfig
from saku.core.encoding import byte_align_encode
from saku.db.models import Document, IndexNGram, create_db_and_tables
from saku.index.parser import DocumentParser

if __name__ == "__main__":
    config = SakuConfig()
    engine = create_engine(config.DATABASE_URI)
    parser = DocumentParser(config.MAX_SPARSE_GRAM_LENGTH)

    session = Session(engine)
    create_db_and_tables(engine)

    docs = []
    tokens = {}

    # Scan for Files
    file_paths = []
    for path in config.SCAN_PATHS:
        files = list(Path(path).rglob("*"))
        file_paths.extend(files)
        print(f"{len(files)} found in {path}")

    for file in file_paths:
        if not file.is_file():
            continue

        file_path = str(file.absolute())
        mime_type = magic.from_file(file_path, mime=True)
        if not mime_type.startswith("text"):
            # Skip non text files
            continue

        file_stat = file.stat()
        file_size = file_stat.st_size
        if file_size > config.max_file_size_to_index_in_bytes:
            # Skip files greater than 10 MB
            continue

        doc = Document(path=file_path, size=file_size)
        docs.append(doc)
        session.add(doc)

    # Save files
    print(f"Found {len(docs)} files to index")
    session.commit()

    for i, doc in enumerate(docs):
        print(f"Indexing {i}th doc: {doc.path}")
        grams = parser.parse_document(doc.path)
        for grm in grams:
            tokens.setdefault(grm, []).append(doc.id)

    print(f"Loading indices into database")
    for ngram, posting_list in tokens.items():
        doc_ids = b"".join(byte_align_encode(posting) for posting in posting_list)
        index_ngram = IndexNGram(ngram=ngram, doc_ids=doc_ids)
        session.add(index_ngram)

    print(f"Saving Indices")
    session.commit()
