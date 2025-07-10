"""
Image generation core module
Contains the main orchestration logic for image generation across different providers
"""

from typing import Optional
from common import DEFAULT_PORT
from tools.utils.image_utils import process_input_image
from ..image_providers.image_base_provider import ImageProviderBase
# 导入所有提供商以确保自动注册 (不要删除这些导入)
from ..image_providers.wraked_provider import WrakedImageProvider
from ..image_providers.openai_provider import OpenAIImageProvider
from ..image_providers.replicate_provider import ReplicateImageProvider
from ..image_providers.volces_provider import VolcesProvider
from ..image_providers.wavespeed_provider import WavespeedProvider
# from ..image_providers.comfyui_provider import ComfyUIProvider
from .image_canvas_utils import (
    save_image_to_canvas,
)

IMAGE_PROVIDERS: dict[str, ImageProviderBase] = {
    'wraked': WrakedImageProvider(),
    'openai': OpenAIImageProvider(),
    'replicate': ReplicateImageProvider(),
    'volces': VolcesProvider(),
    'wavespeed': WavespeedProvider(),
}

async def generate_image_with_provider(
    canvas_id: str,
    session_id: str,
    provider: str,
    model: str,
    # image generator args
    prompt: str,
    aspect_ratio: str,
    input_images: Optional[list[str]] = None,
    **kwargs,
) -> str:
    """
    通用图像生成函数，支持不同的模型和提供商

    Args:
        canvas_id: Canvas ID for saving the generated image
        session_id: Session ID for saving the generated image
        provider: Provider name (e.g., 'replicate', 'openai', 'wraked')
        model: Model identifier (e.g., 'black-forest-labs/flux-kontext-dev')
        prompt: 图像生成提示词
        aspect_ratio: 图像长宽比
        input_images: 可选的输入参考图像列表
        **kwargs: Additional model-specific parameters (go_fast, guidance, output_format, etc.)

    Returns:
        str: 生成结果消息
    """

    provider_instance = IMAGE_PROVIDERS.get(provider)
    if not provider_instance:
        raise ValueError(f"Unknown provider: {provider}")

    # Process input images for the provider
    processed_input_images: list[str] | None = None
    if input_images:
        processed_input_images = []
        for image_path in input_images:
            processed_image = await process_input_image(image_path)
            if processed_image:
                processed_input_images.append(processed_image)

        print(
            f"Using {len(processed_input_images)} input images for generation")
    # Generate image using the selected provider
    mime_type, width, height, filename = await provider_instance.generate(
        prompt=prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        input_images=processed_input_images,
        **kwargs
    )

    # Save image to canvas
    image_url = await save_image_to_canvas(
        session_id, canvas_id, filename, mime_type, width, height
    )

    # Use hardcoded production URL
    base_url = "https://ssss-2-fqku.onrender.com"
    return f"image generated successfully ![image_id: {filename}]({base_url}{image_url})"
