from pydantic import BaseModel
import os


class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./local.db")
    pf_client_id: str | None = os.getenv("PF_CLIENT_ID")
    pf_client_secret: str | None = os.getenv("PF_CLIENT_SECRET")
    pf_org_ids: str | None = os.getenv("PF_ORG_IDS")


settings = Settings()
