import os
import traceback
from typing import Optional, List, Any
from pydantic import BaseModel
from openai.types import Image
from openai import OpenAI, OpenAIError
from .image_base_provider import ImageProviderBase
from ..utils.image_utils import get_image_info_and_save, generate_image_id
from services.config_service import FILES_DIR, config_service


class VolcesImagesResponse(BaseModel):
    """Image response class, Volces API return format, consistent with OpenAI"""
    created: int
    """The Unix timestamp (in seconds) of when the image was created."""

    data: Optional[List[Image]] = None
    """The list of generated images."""


class VolcesProvider(ImageProviderBase):
    """Volces image generation provider implementation"""


    def _create_client(self) -> OpenAI:
        """Create OpenAI client for Volces API"""
        config = config_service.app_config.get('volces', {})
        api_key = str(config.get("api_key", ""))
        api_url = str(config.get("url", ""))

        if not api_key:
            raise ValueError("Volces API key is not configured")
        if not api_url:
            raise ValueError("Volces API URL is not configured")

        return OpenAI(api_key=api_key, base_url=api_url)

    def _calculate_dimensions(self, aspect_ratio: str) -> tuple[int, int]:
        """Calculate width and height based on aspect ratio"""
        w_ratio, h_ratio = map(int, aspect_ratio.split(':'))
        factor = (1024 ** 2 / (w_ratio * h_ratio)) ** 0.5

        width = int((factor * w_ratio) / 64) * 64
        height = int((factor * h_ratio) / 64) * 64

        return width, height

    async def _process_response(self, result: Any, error_prefix: str = "Volces") -> tuple[str, int, int, str]:
        """
        Process OpenAI response and save image

        Args:
            result: OpenAI response object
            error_prefix: Error message prefix

        Returns:
            tuple[str, int, int, str]: (mime_type, width, height, filename)
        """
        if result.data and len(result.data) > 0:
            image_data = result.data[0]
            if hasattr(image_data, 'url') and image_data.url:
                image_url = image_data.url
                image_id = generate_image_id()
                mime_type, width, height, extension = await get_image_info_and_save(
                    image_url,
                    os.path.join(FILES_DIR, f'{image_id}'),
                    is_b64=False
                )

                filename = f'{image_id}.{extension}'
                return mime_type, width, height, filename

        # If no valid image data found
        raise Exception(
            f'{error_prefix} image generation failed: No valid image data in response')

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_images: Optional[list[str]] = None,
        **kwargs: Any
    ) -> tuple[str, int, int, str]:
        """
        Generate image using Volces API service

        Args:
            prompt: Image generation prompt
            model: Model name to use for generation
            aspect_ratio: Image aspect ratio (1:1, 16:9, 4:3, 3:4, 9:16)
            input_images: Optional input images for reference or editing
            **kwargs: Additional provider-specific parameters

        Returns:
            tuple[str, int, int, str]: (mime_type, width, height, filename)
        """
        try:
            # Remove provider prefix from model name
            model = model.replace('volces/', '')

            client = self._create_client()
            width, height = self._calculate_dimensions(aspect_ratio)

            if input_images and len(input_images) > 0:
                # input_image should be the file path for OpenAI
                raise NotImplementedError(
                    "Volces Image Edit are still in progress.")
            else:
                result = client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=kwargs.get("size", f"{width}x{height}"),
                    extra_body={
                        "watermark": False
                    }
                )

            return await self._process_response(result, "Volces")

        except OpenAIError as e:
            print('Error generating image with Volces:', e)
            traceback.print_exc()
            raise e
        except Exception as e:
            print('Error generating image with Volces:', e)
            traceback.print_exc()
            raise e
