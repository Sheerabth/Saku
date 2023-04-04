from pydantic import BaseSettings, Field, PostgresDsn, validator

ONE_MB = 1024 * 1024


class SakuConfig(BaseSettings):
    class Config:
        env_file = ".env"

    # ---- INDEXING
    # Locations to be indexed
    REPO_DIR: str

    # Maximum File that can be considered for Indexing (in MB)
    MAX_FILE_SIZE_TO_INDEX: int = Field(default=10, gt=0)

    # Maximum File that can be considered for Indexing (in MB)
    MAX_SPARSE_GRAM_LENGTH: int = Field(default=3, gt=2)

    @property
    def max_file_size_to_index_in_bytes(self) -> int:
        return self.MAX_FILE_SIZE_TO_INDEX * ONE_MB

    # ---- REDIS
    REDIS_HOST: str
    REDIS_PORT: int

    # ---- DATABASE
    DATABASE_HOST: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    DATABASE_URI: str | None = None

    @validator("DATABASE_URI")
    def construct_database_connection_uri(cls, v: str | None, values: dict[str, str | int]) -> str | PostgresDsn:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            host=values.get("DATABASE_HOST"),
            user=values.get("DATABASE_USER"),
            password=values.get("DATABASE_PASSWORD"),
            path=f"/{values.get('DATABASE_NAME') or ''}",
        )
