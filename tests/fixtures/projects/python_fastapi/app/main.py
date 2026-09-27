from fastapi import FastAPI, HTTPException

app = FastAPI(title="FastAPI Fixture Service")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/v1/auth/login")
def login(payload: dict):
    if payload.get("username") == "admin":
        return {"token": "secret_token_123"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/v1/items")
def list_items():
    return [{"id": 1, "name": "Item 1"}]
