import os
import traceback
from typing import Optional, List, Any
from pydantic import BaseModel
from openai.types import Image
from .image_base_provider import ImageProviderBase
from ..utils.image_utils import get_image_info_and_save, generate_image_id
from services.config_service import FILES_DIR
from utils.http_client import HttpClient
from services.config_service import config_service


class WrakedImagesResponse(BaseModel):
    """Image response class, Wraked API return format, consistent with OpenAI"""
    created: int
    """The Unix timestamp (in seconds) of when the image was created."""

    data: Optional[List[Image]] = None
    """The list of generated images."""


class WrakedImageProvider(ImageProviderBase):
    """Wraked Labs Cloud image generation provider implementation"""

    def _build_url(self) -> str:
        """Build request URL"""
        # Since we're using OpenAI's API endpoint, check OpenAI config
        config = config_service.app_config.get('openai', {})
        api_token = str(config.get("api_key", ""))

        if not api_token:
            raise ValueError("OpenAI API token is not configured")
        
        # Use OpenAI's standard image generation endpoint
        return "https://api.openai.com/v1/images/generations"

    def _build_headers(self) -> dict[str, str]:
        # Since we're using OpenAI's API endpoint, use OpenAI API key
        config = config_service.app_config.get('openai', {})
        api_token = str(config.get("api_key", ""))

        """Build request headers"""
        return {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    async def _make_request(self, url: str, headers: dict[str, str], data: dict[str, Any]) -> WrakedImagesResponse:
        """
        Send HTTP request and handle response

        Returns:
            WrakedImagesResponse: Jaaz compatible image response object
        """
        async with HttpClient.create() as client:
            print(
                f'🦄 Jaaz API request: {url}, model: {data["model"]}, prompt: {data["prompt"]}')
            response = await client.post(url, headers=headers, json=data)

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                print(f'🦄 Jaaz API error: {error_msg}')
                raise Exception(f'Image generation failed: {error_msg}')

            if not response.content:
                raise Exception(
                    'Image generation failed: Empty response from server')

            # Parse JSON data
            json_data = response.json()
            print('🦄 Jaaz API response', json_data)

            return WrakedImagesResponse(**json_data)

    async def _process_response(self, res: WrakedImagesResponse, error_prefix: str = "Jaaz") -> tuple[str, int, int, str]:
        """
        Process ImagesResponse and save image

        Args:
            res: OpenAI ImagesResponse object
            error_prefix: Error message prefix

        Returns:
            tuple[str, int, int, str]: (mime_type, width, height, filename)
        """
        if res.data and len(res.data) > 0:
            image_data = res.data[0]
            if hasattr(image_data, 'url') and image_data.url:
                image_url = image_data.url
                image_id = generate_image_id()
                mime_type, width, height, extension = await get_image_info_and_save(
                    image_url,
                    os.path.join(FILES_DIR, f'{image_id}')
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
        Generate image using Jaaz API service
        Supports both Replicate format and OpenAI format models

        Returns:
            tuple[str, int, int, str]: (mime_type, width, height, filename)
        """
        # Check if it's an OpenAI model
        if model.startswith('openai/'):
            return await self._generate_openai_image(
                prompt=prompt,
                model=model,
                input_images=input_images,
                aspect_ratio=aspect_ratio,
                **kwargs
            )

        # Replicate compatible logic
        return await self._generate_replicate_image(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            input_images=input_images,
            **kwargs
        )

    async def _generate_replicate_image(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_images: Optional[list[str]] = None,
        **kwargs: Any
    ) -> tuple[str, int, int, str]:
        """Generate Replicate format image"""
        try:
            url = self._build_url()
            headers = self._build_headers()

            # Build request data, consistent with Replicate format
            data = {
                "prompt": prompt,
                "model": model,
                "aspect_ratio": aspect_ratio,
            }

            # Add input images if provided
            if input_images:
                # For Replicate format, we take the first image as input_image
                data['input_image'] = input_images[0]
                if len(input_images) > 1:
                    print(
                        "Warning: Replicate format only supports single image input. Using first image.")

            res = await self._make_request(url, headers, data)
            return await self._process_response(res, "Jaaz")

        except Exception as e:
            print('Error generating image with Jaaz:', e)
            traceback.print_exc()
            raise e

    async def _generate_openai_image(
        self,
        prompt: str,
        model: str,
        input_images: Optional[list[str]] = None,
        aspect_ratio: str = "1:1",
        **kwargs: Any
    ) -> tuple[str, int, int, str]:
        """
        Generate image using Jaaz API service calling OpenAI model
        Compatible with OpenAI image generation API

        Returns:
            tuple[str, int, int, str]: (mime_type, width, height, filename)
        """
        try:
            url = self._build_url()
            headers = self._build_headers()

            # Build request data according to OpenAI Image API format
            enhanced_prompt = f"{prompt} Aspect ratio: {aspect_ratio}"
            
            # Remove provider prefix from model name (openai/gpt-image-1 -> gpt-image-1)
            clean_model = model.split('/')[-1] if '/' in model else model

            data = {
                "model": clean_model,
                "prompt": enhanced_prompt,
                "n": kwargs.get("num_images", 1),
                "size": "1024x1024",  # OpenAI standard size
                "quality": "low"  # Low quality for faster generation
            }

            # Add input images if provided (not supported for gpt-image-1 generation)
            if input_images:
                print(f"Warning: input_images not supported for gpt-image-1 generation, ignoring {len(input_images)} input images")

            res = await self._make_request(url, headers, data)
            return await self._process_response(res, "Jaaz OpenAI")

        except Exception as e:
            print('Error generating image with Jaaz OpenAI:', e)
            traceback.print_exc()
            raise e
