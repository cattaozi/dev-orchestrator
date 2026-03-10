from fastapi import APIRouter
from services import config_service

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def get_config():
    return config_service.get_config()


@router.post("/config")
def update_config(config_data: dict):
    config_service.update_config(config_data)
    return {"message": "Config updated"}