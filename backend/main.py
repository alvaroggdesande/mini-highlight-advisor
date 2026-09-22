from fastapi import FastAPI

app = FastAPI(title="Mini Highlight Advisor API")

@app.get("/api/health")
def health():
    return {"status": "ok"}
