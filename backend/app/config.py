from pydantic import BaseModel
from typing import Optional
import os

class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./local.db")
    pf_client_id: Optional[str] = os.getenv("PF_CLIENT_ID")
    pf_client_secret: Optional[str] = os.getenv("PF_CLIENT_SECRET")
    pf_org_ids: Optional[str] = os.getenv("PF_ORG_IDS")

settings = Settings()
