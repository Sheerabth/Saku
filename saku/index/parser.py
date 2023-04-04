from typing import Iterator

from code_tokenize import tokenize as code_tokenize
from nltk import bigrams

MAX_INDEX_LINE_LENGTH = 512


class DocumentParser:
    def __init__(self, max_sparse_gram_length: int):
        self._max_sparse_gram_length = max_sparse_gram_length

    @staticmethod
    def _weigh_token(token: str) -> list[int]:
        return [sum(ord(grm) for grm in bigram) for bigram in list(bigrams(token))]

    def generate_index_grams(self, token: str) -> Iterator[str]:
        weights = self._weigh_token(token)

        for start, start_wt in enumerate(weights[:-1]):
            max_wt = -1
            for end in range(start + 1, min(start + self._max_sparse_gram_length, len(weights))):
                current_wt = weights[end]
                if max_wt < current_wt:
                    yield token[start : end + 2]

                    if start_wt == current_wt:
                        continue

                    max_wt = current_wt
                    if start_wt < max_wt:
                        break

    @staticmethod
    def ast_tokenize(fp) -> Iterator[str]:
        content = fp.read()
        if content:
            tokens = code_tokenize(content, lang="python", syntax_error="warning")
            for token in tokens:
                if token.type in ["newline"]:
                    continue

                yield token.text

    @staticmethod
    def line_tokenize(fp) -> Iterator[str]:
        for line in fp.readlines():
            if len(line) > MAX_INDEX_LINE_LENGTH:
                continue
            yield line

    @staticmethod
    def chunk_tokenize(fp, chunk_size: int = 16) -> Iterator[str]:
        while True:
            chunk = fp.read(chunk_size)
            if not chunk:
                break
            yield chunk

    @staticmethod
    def no_tokenize(fp) -> Iterator[str]:
        yield fp.read()

    def parse_document(self, file_path: str) -> set[str]:
        document_grams = set()

        with open(file_path) as fp:
            try:
                for token in self.no_tokenize(fp):
                    token_grams = self.generate_index_grams(token)
                    document_grams.update(token_grams)
            except UnicodeDecodeError:
                print("UnicodeDecodeError ", file_path)

        return document_grams
