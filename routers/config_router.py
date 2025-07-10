from fastapi import APIRouter, Request
from services.config_service import config_service
# from tools.video_models_dynamic import register_video_models  # Disabled video models

router = APIRouter(prefix="/api/config")


@router.get("/exists")
async def config_exists():
    return {"exists": config_service.exists_config()}


@router.get("")
async def get_config():
    return config_service.app_config


@router.post("")
async def update_config(request: Request):
    data = await request.json()
    res = await config_service.update_config(data)
    return res
