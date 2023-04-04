from typing import Iterable


def chunk(lst: list, chunk_size: int) -> Iterable[list]:
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]


def un_chunk(chunks: list[list]) -> list:
    return [item for chk in chunks for item in chk]
