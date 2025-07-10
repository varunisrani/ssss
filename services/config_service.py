import copy
import os
import traceback
import aiofiles
import toml
from typing import Dict, Literal, Optional
from typing_extensions import TypedDict

# 定义配置文件的类型结构

class ModelConfig(TypedDict, total=False):
    type: Literal["text", "image", "video"]
    is_custom: Optional[bool]
    is_disabled: Optional[bool]


class ProviderConfig(TypedDict, total=False):
    url: str
    api_key: str
    max_tokens: int
    models: Dict[str, ModelConfig]
    is_custom: Optional[bool]


AppConfig = Dict[str, ProviderConfig]


DEFAULT_PROVIDERS_CONFIG: AppConfig = {
    'wraked': {
        'models': {
            # text models
            'gpt-4o': {'type': 'text'},
            'gpt-4o-mini': {'type': 'text'},
            'deepseek/deepseek-chat-v3-0324': {'type': 'text'},
            'anthropic/claude-sonnet-4': {'type': 'text'},
            'anthropic/claude-3.7-sonnet': {'type': 'text'},
            # image models
            'openai/gpt-image-1': {'type': 'image'},
        },
        'url': os.getenv('BASE_API_URL', 'https://www.wraked.app').rstrip('/') + '/api/v1/',
        'api_key': '',
        'max_tokens': 8192,
    },
    'comfyui': {
        'models': {},
        'url': 'http://127.0.0.1:8188',
        'api_key': '',
    },
    'ollama': {
        'models': {},
        'url': 'http://localhost:11434',
        'api_key': '',
        'max_tokens': 8192,
    },
    'openai': {
        'models': {
            'gpt-4o': {'type': 'text'},
            'gpt-4o-mini': {'type': 'text'},
            'gpt-image-1': {'type': 'image'},
        },
        'url': 'https://api.openai.com/v1/',
        'api_key': '',
        'max_tokens': 8192,
    },
    'replicate': {
        'models': {
            'imagen-4': {'type': 'image'},
            'recraft-v3': {'type': 'image'},
            'flux-kontext-pro': {'type': 'image'},
            'flux-kontext-max': {'type': 'image'},
        },
        'url': 'https://api.replicate.com/v1/',
        'api_key': '',
        'max_tokens': 8192,
    },
    'volces': {
        'models': {
            'doubao-seedream-3': {'type': 'image'},
            'seedance-v1-pro': {'type': 'video'},
            'seedance-v1-lite-t2v': {'type': 'video'},
            'seedance-v1-lite-i2v': {'type': 'video'},
        },
        'url': 'https://open.volcengineapi.com/',
        'api_key': '',
        'max_tokens': 8192,
    },

}

SERVER_DIR = os.path.dirname(os.path.dirname(__file__))
USER_DATA_DIR = os.getenv(
    "USER_DATA_DIR",
    os.path.join(SERVER_DIR, "user_data"),
)
FILES_DIR = os.path.join(USER_DATA_DIR, "files")


IMAGE_FORMATS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",  # 基础格式
    ".bmp",
    ".tiff",
    ".tif",  # 其他常见格式
    ".webp",
)
VIDEO_FORMATS = (
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
    ".flv",
)


class ConfigService:
    def __init__(self):
        self.app_config: AppConfig = copy.deepcopy(DEFAULT_PROVIDERS_CONFIG)
        self.config_file = os.getenv(
            "CONFIG_PATH", os.path.join(USER_DATA_DIR, "config.toml")
        )
        self.initialized = False

    async def initialize(self) -> None:
        try:
            # Ensure the user_data directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            # Check if config file exists
            if not self.exists_config():
                print(
                    f"Config file not found at {self.config_file}, creating default configuration")
                # Create default config file
                with open(self.config_file, "w") as f:
                    toml.dump(self.app_config, f)
                print(f"Default config file created at {self.config_file}")
                self.initialized = True
                return

            async with aiofiles.open(self.config_file, "r") as f:
                content = await f.read()
                config: AppConfig = toml.loads(content)
            for provider, provider_config in config.items():
                if provider not in DEFAULT_PROVIDERS_CONFIG:
                    provider_config['is_custom'] = True
                self.app_config[provider] = provider_config
                # image/video models are hardcoded in the default provider config
                provider_models = DEFAULT_PROVIDERS_CONFIG.get(
                    provider, {}).get('models', {})
                for model_name, model_config in provider_config.get('models', {}).items():
                    # Only text model can be self added
                    if model_config.get('type') == 'text' and model_name not in provider_models:
                        provider_models[model_name] = model_config
                        provider_models[model_name]['is_custom'] = True
                self.app_config[provider]['models'] = provider_models
                
            # Load API keys from environment variables if not set in config
            env_api_keys = {
                'replicate': os.getenv('REPLICATE_API_KEY'),
                'openai': os.getenv('OPENAI_API_KEY'),
                'wraked': os.getenv('WRAKED_API_KEY'),
                'volces': os.getenv('VOLCES_API_KEY'),
            }
            
            for provider, env_api_key in env_api_keys.items():
                if env_api_key and provider in self.app_config:
                    if not self.app_config[provider].get('api_key', '').strip():
                        self.app_config[provider]['api_key'] = env_api_key
                        print(f"Using API key from environment for {provider}")
        except Exception as e:
            print(f"Error loading config: {e}")
            traceback.print_exc()
        finally:
            self.initialized = True

    def get_config(self) -> AppConfig:
        # 直接返回内存中的配置
        return self.app_config

    async def update_config(self, data: AppConfig) -> Dict[str, str]:
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, "w") as f:
                toml.dump(data, f)
            self.app_config = data

            return {
                "status": "success",
                "message": "Configuration updated successfully",
            }
        except Exception as e:
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def exists_config(self) -> bool:
        return os.path.exists(self.config_file)

    async def add_image_model(self, provider: str, model_name: str, model_type: str = "image", api_key: str = "", url: str = "") -> Dict[str, str]:
        """
        动态添加图像模型到配置中
        
        Args:
            provider: 提供商名称
            model_name: 模型名称
            model_type: 模型类型 (默认为 "image")
            api_key: API密钥
            url: 提供商URL
            
        Returns:
            dict: 操作结果
        """
        try:
            # 如果提供商不存在，创建新的提供商配置
            if provider not in self.app_config:
                self.app_config[provider] = {
                    'models': {},
                    'url': url or '',
                    'api_key': api_key or '',
                    'max_tokens': 8192,
                    'is_custom': True
                }
            
            # 如果提供了API密钥，更新提供商的API密钥
            if api_key:
                self.app_config[provider]['api_key'] = api_key
            
            # 如果提供了URL，更新提供商的URL
            if url:
                self.app_config[provider]['url'] = url
            
            # 添加模型到提供商配置
            if 'models' not in self.app_config[provider]:
                self.app_config[provider]['models'] = {}
                
            self.app_config[provider]['models'][model_name] = {
                'type': model_type,
                'is_custom': True
            }
            
            # 保存配置到文件
            await self._save_config()
            
            return {
                "status": "success",
                "message": f"Image model '{model_name}' added to provider '{provider}' successfully"
            }
            
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Failed to add image model: {str(e)}"
            }

    async def remove_image_model(self, provider: str, model_name: str) -> Dict[str, str]:
        """
        从配置中移除图像模型
        
        Args:
            provider: 提供商名称
            model_name: 模型名称
            
        Returns:
            dict: 操作结果
        """
        try:
            if provider not in self.app_config:
                return {
                    "status": "error",
                    "message": f"Provider '{provider}' not found"
                }
            
            if 'models' not in self.app_config[provider]:
                return {
                    "status": "error",
                    "message": f"No models found for provider '{provider}'"
                }
            
            if model_name not in self.app_config[provider]['models']:
                return {
                    "status": "error",
                    "message": f"Model '{model_name}' not found in provider '{provider}'"
                }
            
            # 只能删除自定义模型
            model_config = self.app_config[provider]['models'][model_name]
            if not model_config.get('is_custom', False):
                return {
                    "status": "error",
                    "message": f"Cannot remove built-in model '{model_name}'"
                }
            
            # 删除模型
            del self.app_config[provider]['models'][model_name]
            
            # 保存配置到文件
            await self._save_config()
            
            return {
                "status": "success",
                "message": f"Image model '{model_name}' removed from provider '{provider}' successfully"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to remove image model: {str(e)}"
            }

    async def update_provider_api_key(self, provider: str, api_key: str) -> Dict[str, str]:
        """
        更新提供商的API密钥
        
        Args:
            provider: 提供商名称
            api_key: 新的API密钥
            
        Returns:
            dict: 操作结果
        """
        try:
            if provider not in self.app_config:
                return {
                    "status": "error",
                    "message": f"Provider '{provider}' not found"
                }
            
            self.app_config[provider]['api_key'] = api_key
            
            # 保存配置到文件
            await self._save_config()
            
            return {
                "status": "success",
                "message": f"API key updated for provider '{provider}' successfully"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to update API key: {str(e)}"
            }

    async def _save_config(self) -> None:
        """
        保存配置到文件
        """
        try:
            # 创建要保存的配置副本，排除默认模型
            config_to_save = {}
            
            for provider, provider_config in self.app_config.items():
                # 只保存有API密钥的提供商或自定义提供商
                if provider_config.get('api_key') or provider_config.get('is_custom'):
                    config_to_save[provider] = {
                        'url': provider_config.get('url', ''),
                        'api_key': provider_config.get('api_key', ''),
                        'max_tokens': provider_config.get('max_tokens', 8192)
                    }
                    
                    # 只保存自定义模型
                    custom_models = {}
                    for model_name, model_config in provider_config.get('models', {}).items():
                        if model_config.get('is_custom'):
                            custom_models[model_name] = {
                                'type': model_config.get('type', 'text'),
                                'is_custom': True
                            }
                    
                    if custom_models:
                        config_to_save[provider]['models'] = custom_models
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # 保存到文件
            with open(self.config_file, "w") as f:
                toml.dump(config_to_save, f)
                
        except Exception as e:
            print(f"Error saving config: {e}")
            traceback.print_exc()
            raise


config_service = ConfigService()
