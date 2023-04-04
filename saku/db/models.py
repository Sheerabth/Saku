from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    path: str = Field(unique=True)
    size: int
    mime_type: str
    last_modified: datetime
    last_indexed: Optional[datetime] = None


class IndexNGram(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ngram: str = Field(unique=True, index=True)
    doc_ids: Optional[bytes] = None
    last_updated: Optional[datetime] = None


def create_db_and_tables(engine):
    SQLModel.metadata.create_all(engine)
