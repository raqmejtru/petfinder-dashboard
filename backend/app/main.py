from fastapi import FastAPI

app = FastAPI(title="Petfinder Dashboard API")

@app.get("/health")
def health():
    return {"ok": True}
