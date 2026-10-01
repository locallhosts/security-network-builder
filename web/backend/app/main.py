from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Security Network Builder API")

class SearchRequest(BaseModel):
    query: str

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "security-network-builder"}

@app.post("/api/search")
def search(request: SearchRequest):
    return {
        "query": request.query,
        "results": [],
        "message": "Connect this endpoint to the SNB intelligence engine"
    }

@app.get("/api/network")
def network():
    return {
        "nodes": [],
        "edges": []
    }
