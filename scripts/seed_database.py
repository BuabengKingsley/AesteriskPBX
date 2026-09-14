from app.database.base import Base
from app.database.seed import seed_database
from app.database.session import SessionLocal, engine


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_database(session)
    print("Synthetic development data is ready.")

