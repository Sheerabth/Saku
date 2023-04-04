from sqlmodel import Session, create_engine


class DbConnector:
    def __init__(self, database_uri: str):
        self.engine = create_engine(database_uri)

    def get_session(self) -> Session:
        session = Session(bind=self.engine)
        return session
