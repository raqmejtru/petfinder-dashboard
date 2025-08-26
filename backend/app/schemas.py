from pydantic import BaseModel

class OrgMetric(BaseModel):
    org_id: str
    impact_index: float | None = None
