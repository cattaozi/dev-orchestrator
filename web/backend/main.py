from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize database
from db import init_db
init_db()

# Import routers
from routers import projects, prds, issues, workers, sessions, config

app = FastAPI(title="DevOrchestrator API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router)
app.include_router(prds.router)
app.include_router(issues.router)
app.include_router(workers.router)
app.include_router(sessions.router)
app.include_router(config.router)


@app.get("/")
def root():
    return {"message": "DevOrchestrator API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)