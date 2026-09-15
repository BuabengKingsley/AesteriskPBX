from app.database.seed import seed_database
from app.database.session import SessionLocal


if __name__ == "__main__":
    with SessionLocal() as session:
        seed_database(session)
    print("Synthetic development data is ready.")

