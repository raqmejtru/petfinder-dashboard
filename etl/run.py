# Minimal ETL placeholder: proves wiring works.
from backend.app.db import SessionLocal

def run_once():
    with SessionLocal() as _:
        print("ETL OK (placeholder)")

if __name__ == "__main__":
    run_once()
