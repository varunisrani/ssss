"""
Settings Router - 设置路由模块 (Frontend-Friendly Version)

该模块提供设置相关的 API 路由端点，特别针对前端图像模型管理优化
"""

import json
import os
import shutil
import httpx
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from services.db_service import db_service
from services.settings_service import settings_service
from services.tool_service import tool_service
from services.knowledge_service import list_user_enabled_knowledge
from services.config_service import config_service
from pydantic import BaseModel

# 创建设置相关的路由器，所有端点都以 /api/settings 为前缀
router = APIRouter(prefix="/api/settings")


class ImageModelRequest(BaseModel):
    provider: str
    model_name: str
    model_type: str = "image"
    api_key: str = ""
    url: str = ""


class ProviderConfigRequest(BaseModel):
    api_key: str
    url: str = ""


class ModelToggleRequest(BaseModel):
    enabled: bool


# =============================================================================
# 原有的设置端点
# =============================================================================

@router.get("/exists")
async def settings_exists():
    """检查设置文件是否存在"""
    return {"exists": await settings_service.exists_settings()}


@router.get("")
async def get_settings():
    """获取所有设置配置"""
    return settings_service.get_settings()


@router.post("")
async def update_settings(request: Request):
    """更新设置配置"""
    data = await request.json()
    result = await settings_service.update_settings(data)
    return result


@router.get("/proxy/status")
async def get_proxy_status():
    """获取代理配置状态"""
    settings = settings_service.get_raw_settings()
    proxy_setting = settings.get('proxy', '')

    if proxy_setting == '':
        return {"enable": False, "configured": True, "message": "Proxy is disabled"}
    elif proxy_setting == 'system':
        return {"enable": True, "configured": True, "message": "Using system proxy"}
    elif proxy_setting.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
        return {"enable": True, "configured": True, "message": "Using custom proxy"}
    else:
        return {"enable": True, "configured": False, "message": "Proxy configuration is invalid"}


@router.get("/proxy")
async def get_proxy_settings():
    """获取代理设置"""
    proxy_config = settings_service.get_proxy_config()
    return {"proxy": proxy_config}


@router.post("/proxy")
async def update_proxy_settings(request: Request):
    """更新代理设置"""
    proxy_data = await request.json()
    
    if not isinstance(proxy_data, dict) or "proxy" not in proxy_data:
        raise HTTPException(status_code=400, detail="Invalid proxy configuration")
    
    proxy_value = proxy_data["proxy"]
    
    if not isinstance(proxy_value, str):
        raise HTTPException(status_code=400, detail="Proxy value must be a string")
    
    if proxy_value not in ['', 'system'] and not proxy_value.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
        raise HTTPException(status_code=400, detail="Invalid proxy value")
    
    result = await settings_service.update_settings({"proxy": proxy_value})
    return result


@router.get("/knowledge/enabled")
async def get_enabled_knowledge():
    """获取启用的知识库列表"""
    try:
        knowledge_list = list_user_enabled_knowledge()
        return {"success": True, "data": knowledge_list, "count": len(knowledge_list)}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


# =============================================================================
# 图像提供商管理端点 (前端友好)
# =============================================================================

@router.get("/image_providers")
async def get_image_providers():
    """
    获取所有图像提供商的配置状态 (前端设置页面专用)
    
    Returns:
        dict: 所有图像提供商的详细配置信息
    """
    try:
        config = config_service.get_config()
        providers = []
        
        # 预定义的图像提供商信息
        provider_info = {
            "wraked": {
                "display_name": "Jaaz",
                "description": "Access to GPT-image-1 and other models via Jaaz API",
                "website": "https://www.wraked.app",
                "setup_url": "https://www.wraked.app/dashboard",
                "icon": "🚀",
                "featured_models": ["openai/gpt-image-1"]
            },
            "openai": {
                "display_name": "OpenAI",
                "description": "Direct access to OpenAI image models",
                "website": "https://openai.com",
                "setup_url": "https://platform.openai.com/api-keys",
                "icon": "🤖",
                "featured_models": ["gpt-image-1"]
            },
            "replicate": {
                "display_name": "Replicate",
                "description": "AI models including Flux, Imagen, and Recraft",
                "website": "https://replicate.com",
                "setup_url": "https://replicate.com/account/api-tokens",
                "icon": "🔄",
                "featured_models": ["flux-kontext-pro", "imagen-4", "recraft-v3"]
            },
            "volces": {
                "display_name": "Volces",
                "description": "ByteDance AI models including Doubao series",
                "website": "https://www.volcengine.com",
                "setup_url": "https://console.volcengine.com/",
                "icon": "🌋",
                "featured_models": ["doubao-seedream-3"]
            },
            "comfyui": {
                "display_name": "ComfyUI",
                "description": "Local image generation with custom workflows",
                "website": "https://github.com/comfyanonymous/ComfyUI",
                "setup_url": "https://github.com/comfyanonymous/ComfyUI#installing",
                "icon": "🎨",
                "featured_models": ["Custom Workflows"]
            }
        }
        
        for provider_name, provider_config in config.items():
            if provider_name not in provider_info:
                continue
                
            has_api_key = bool(provider_config.get('api_key', ''))
            models = provider_config.get('models', {})
            
            # 统计图像模型
            image_models = [m for m, cfg in models.items() if cfg.get('type') == 'image']
            enabled_models = [m for m, cfg in models.items() if cfg.get('type') == 'image' and not cfg.get('is_disabled')]
            
            provider_data = {
                "provider": provider_name,
                "display_name": provider_info[provider_name]["display_name"],
                "description": provider_info[provider_name]["description"],
                "website": provider_info[provider_name]["website"],
                "setup_url": provider_info[provider_name]["setup_url"],
                "icon": provider_info[provider_name]["icon"],
                "featured_models": provider_info[provider_name]["featured_models"],
                "url": provider_config.get('url', ''),
                "has_api_key": has_api_key,
                "api_key_configured": has_api_key,
                "status": "configured" if has_api_key else "not_configured",
                "total_models": len(image_models),
                "enabled_models": len(enabled_models),
                "models": image_models,
                "requires_api_key": provider_name != "comfyui"
            }
            
            providers.append(provider_data)
        
        return {
            "success": True,
            "data": providers,
            "total_providers": len(providers)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": []
        }


@router.post("/image_providers/{provider_name}/configure")
async def configure_image_provider(provider_name: str, request: ProviderConfigRequest):
    """
    配置图像提供商 (前端设置页面专用)
    
    Args:
        provider_name: 提供商名称
        request: 配置请求数据
        
    Returns:
        dict: 配置结果
    """
    try:
        # 更新API密钥
        result = await config_service.update_provider_api_key(provider_name, request.api_key)
        
        if result.get("status") == "success":
            # 如果提供了URL，也更新URL
            if request.url:
                config = config_service.get_config()
                if provider_name in config:
                    config[provider_name]["url"] = request.url
                    await config_service._save_config()
            
            # 重新初始化工具服务
            await tool_service.initialize()
            
            return {
                "success": True,
                "message": f"Provider '{provider_name}' configured successfully",
                "provider": provider_name,
                "configured": True
            }
        else:
            return {
                "success": False,
                "error": result.get("message", "Configuration failed")
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/image_models")
async def get_image_models():
    """
    获取所有已配置的图像模型 (前端友好格式)
    
    Returns:
        dict: 包含所有图像模型的列表，按提供商分组
    """
    try:
        config = config_service.get_config()
        providers_data = []
        
        for provider_name, provider_config in config.items():
            has_api_key = bool(provider_config.get('api_key', ''))
            models = provider_config.get('models', {})
            
            # 获取该提供商的图像模型
            image_models = []
            for model_name, model_config in models.items():
                if model_config.get('type') == 'image':
                    image_models.append({
                        "name": model_name,
                        "display_name": model_config.get('display_name', model_name),
                        "type": model_config.get('type', 'image'),
                        "enabled": has_api_key and not model_config.get('is_disabled', False),
                        "is_custom": model_config.get('is_custom', False),
                        "is_built_in": not model_config.get('is_custom', False)
                    })
            
            # 只返回有图像模型的提供商
            if image_models:
                providers_data.append({
                    "provider": provider_name,
                    "provider_display_name": provider_name.title(),
                    "url": provider_config.get('url', ''),
                    "has_api_key": has_api_key,
                    "api_key_masked": '*' * 8 if has_api_key else '',
                    "models": image_models,
                    "models_count": len(image_models),
                    "enabled_models_count": len([m for m in image_models if m['enabled']])
                })
        
        return {
            "success": True,
            "data": providers_data,
            "total_providers": len(providers_data),
            "total_models": sum(p['models_count'] for p in providers_data)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": []
        }


@router.post("/image_models/{provider}/{model_name}/toggle")
async def toggle_image_model(provider: str, model_name: str, request: ModelToggleRequest):
    """
    启用/禁用图像模型 (前端设置页面专用)
    
    Args:
        provider: 提供商名称
        model_name: 模型名称
        request: 切换请求数据
        
    Returns:
        dict: 操作结果
    """
    try:
        config = config_service.get_config()
        
        if provider not in config:
            return {
                "success": False,
                "error": f"Provider '{provider}' not found"
            }
            
        if model_name not in config[provider].get('models', {}):
            return {
                "success": False,
                "error": f"Model '{model_name}' not found in provider '{provider}'"
            }
        
        # 更新模型状态
        config[provider]['models'][model_name]['is_disabled'] = not request.enabled
        
        # 保存配置
        await config_service._save_config()
        
        # 重新初始化工具服务
        await tool_service.initialize()
        
        return {
            "success": True,
            "message": f"Model '{model_name}' {'enabled' if request.enabled else 'disabled'} successfully",
            "provider": provider,
            "model": model_name,
            "enabled": request.enabled
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/image_models")
async def add_image_model(request: ImageModelRequest):
    """
    添加新的图像模型
    
    Args:
        request: 图像模型请求数据
        
    Returns:
        dict: 操作结果
    """
    try:
        # 验证必填字段
        if not request.provider or not request.model_name:
            raise HTTPException(
                status_code=400,
                detail="Provider and model_name are required"
            )
        
        # 更新配置
        result = await config_service.add_image_model(
            provider=request.provider,
            model_name=request.model_name,
            model_type=request.model_type,
            api_key=request.api_key,
            url=request.url
        )
        
        if result.get("success"):
            # 重新初始化工具服务以注册新模型
            await tool_service.initialize()
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.delete("/image_models/{provider}/{model_name}")
async def remove_image_model(provider: str, model_name: str):
    """
    移除图像模型
    
    Args:
        provider: 提供商名称
        model_name: 模型名称
        
    Returns:
        dict: 操作结果
    """
    try:
        result = await config_service.remove_image_model(provider, model_name)
        
        if result.get("success"):
            # 重新初始化工具服务
            await tool_service.initialize()
            
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/image_models/available")
async def get_available_image_models():
    """
    获取所有可用的图像模型 (用于前端模型选择器)
    
    Returns:
        dict: 所有可用的图像模型列表
    """
    try:
        config = config_service.get_config()
        available_models = []
        
        for provider_name, provider_config in config.items():
            has_api_key = bool(provider_config.get('api_key', ''))
            models = provider_config.get('models', {})
            
            for model_name, model_config in models.items():
                if (model_config.get('type') == 'image' and 
                    has_api_key and 
                    not model_config.get('is_disabled', False)):
                    
                    available_models.append({
                        "id": f"{provider_name}:{model_name}",
                        "provider": provider_name,
                        "model_name": model_name,
                        "display_name": model_config.get('display_name', model_name),
                        "provider_display_name": provider_name.title(),
                        "full_name": f"{provider_name.title()} - {model_config.get('display_name', model_name)}",
                        "is_custom": model_config.get('is_custom', False)
                    })
        
        return {
            "success": True,
            "data": available_models,
            "count": len(available_models)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": []
        }


# =============================================================================
# ComfyUI 端点保持不变
# =============================================================================

class CreateWorkflowRequest(BaseModel):
    name: str
    api_json: dict
    description: str
    inputs: list
    outputs: str = None


@router.post("/comfyui/create_workflow")
async def create_workflow(request: CreateWorkflowRequest):
    if not request.name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not request.api_json:
        raise HTTPException(status_code=400, detail="API JSON is required")
    if not request.description:
        raise HTTPException(status_code=400, detail="Description is required")
    if not request.inputs:
        raise HTTPException(status_code=400, detail="Inputs are required")
    try:
        name = request.name.replace(" ", "_")
        api_json = json.dumps(request.api_json)
        inputs = json.dumps(request.inputs)
        outputs = json.dumps(request.outputs)
        await db_service.create_comfy_workflow(name, api_json, request.description, inputs, outputs)
        await tool_service.initialize()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create workflow: {str(e)}")


@router.get("/comfyui/list_workflows")
async def list_workflows():
    return await db_service.list_comfy_workflows()


@router.delete("/comfyui/delete_workflow/{id}")
async def delete_workflow(id: int):
    result = await db_service.delete_comfy_workflow(id)
    await tool_service.initialize()
    return result


@router.post("/comfyui/proxy")
async def comfyui_proxy(request: Request):
    try:
        data = await request.json()
        target_url = data.get("url")
        path = data.get("path", "")

        if not target_url or not path:
            raise HTTPException(status_code=400, detail="Missing 'url' or 'path' in request body")

        full_url = f"{target_url}{path}"

        async with httpx.AsyncClient() as client:
            response = await client.get(full_url)
            return response.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy request failed: {str(e)}")