import os
import traceback
from typing import Optional, Any
from .image_base_provider import ImageProviderBase
from ..utils.image_utils import get_image_info_and_save, generate_image_id
from services.config_service import FILES_DIR
from utils.http_client import HttpClient
from services.config_service import config_service

class ReplicateImageProvider(ImageProviderBase):
    """Replicate image generation provider implementation"""

    def _build_url(self, model: str) -> str:
        """Build request URL for Replicate API"""
        return f"https://api.replicate.com/v1/models/{model}/predictions"

    def _build_headers(self) -> dict[str, str]:
        """Build request headers"""
        config = config_service.app_config.get('replicate', {})
        api_key = config.get("api_key", "")

        if not api_key:
            raise ValueError("Replicate API key is not configured")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "wait"
        }

    async def _make_request(self, url: str, headers: dict[str, str], data: dict[str, Any]) -> dict[str, Any]:
        """
        Send HTTP request and handle response

        Returns:
            dict[str, Any]: Response data from Replicate API
        """
        async with HttpClient.create() as client:
            print(
                f'🦄 Replicate API request: {url}, model: {data["input"]["prompt"]}')
            response = await client.post(url, headers=headers, json=data)

            if not response.content:
                raise Exception(
                    'Image generation failed: Empty response from server')

            # Parse JSON data
            json_data = response.json()
            print('🦄 Replicate API response', json_data)

            return json_data

    async def _process_response(self, res: dict[str, Any]) -> tuple[str, int, int, str]:
        """
        Process Replicate API response and save image

        Args:
            res: Response data from Replicate API

        Returns:
            tuple[str, int, int, str]: (mime_type, width, height, filename)
        """
        output = res.get('output', '')
        if output == '':
            if res.get('detail', '') != '':
                raise Exception(
                    f'Replicate image generation failed: {res.get("detail", "")}')
            else:
                raise Exception(
                    'Replicate image generation failed: no output url found')

        image_id = generate_image_id()
        print('🦄 image generation image_id', image_id)

        # Get image dimensions and save
        mime_type, width, height, extension = await get_image_info_and_save(
            output, os.path.join(FILES_DIR, f'{image_id}')
        )

        filename = f'{image_id}.{extension}'
        return mime_type, width, height, filename

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_images: Optional[list[str]] = None,
        **kwargs: Any
    ) -> tuple[str, int, int, str]:
        """
        Generate image using Replicate API

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
            url = self._build_url(model)
            headers = self._build_headers()

            # Build request data
            data = {
                "input": {
                    "prompt": prompt,
                }
            }
            
            # Add model-specific parameters
            if "ideogram-ai/ideogram-v3-turbo" in model:
                # Ideogram V3 Turbo specific parameters
                data["input"].update({
                    "resolution": "None",
                    "style_type": "None", 
                    "magic_prompt_option": "Auto",
                    "quality": "low",  # Set low quality for faster generation
                    "aspect_ratio": aspect_ratio
                })
            elif "black-forest-labs/flux-dev" in model:
                # Flux Dev specific parameters
                data["input"].update({
                    "guidance_scale": 2.5,
                    "num_inference_steps": 30,
                    "aspect_ratio": aspect_ratio
                })
            elif "black-forest-labs/flux-kontext-dev" in model:
                # Flux Kontext Dev specific parameters for image editing
                data["input"].update({
                    "go_fast": kwargs.get("go_fast", True),
                    "guidance": kwargs.get("guidance", 2.5),
                    "aspect_ratio": aspect_ratio,
                    "output_format": kwargs.get("output_format", "jpg"),
                    "output_quality": kwargs.get("output_quality", 80),
                    "num_inference_steps": kwargs.get("num_inference_steps", 30)
                })
            elif "black-forest-labs/flux-kontext-pro" in model:
                # Flux Kontext Pro specific parameters for image editing
                data["input"].update({
                    "aspect_ratio": aspect_ratio,
                    "output_format": kwargs.get("output_format", "jpg"),
                    "safety_tolerance": kwargs.get("safety_tolerance", 2),
                    "prompt_upsampling": kwargs.get("prompt_upsampling", False)
                })
            elif "bytedance/seedream-3" in model:
                # Seedream 3 specific parameters
                data["input"].update({
                    "size": "regular",
                    "guidance_scale": 2.5,
                    "aspect_ratio": aspect_ratio
                })
                # Map aspect ratios to width/height for Seedream 3
                aspect_to_dimensions = {
                    "1:1": {"width": 2048, "height": 2048},
                    "16:9": {"width": 2048, "height": 1152},
                    "4:3": {"width": 2048, "height": 1536},
                    "3:4": {"width": 1536, "height": 2048},
                    "9:16": {"width": 1152, "height": 2048}
                }
                dimensions = aspect_to_dimensions.get(aspect_ratio, {"width": 2048, "height": 2048})
                data["input"].update(dimensions)
            else:
                # Default for other models (like existing Flux, Imagen, Recraft models)
                data["input"]["aspect_ratio"] = aspect_ratio

            if input_images:
                # For Replicate format, we take the first image as input_image
                data['input']['input_image'] = input_images[0]
                if len(input_images) > 1:
                    print(
                        "Warning: Replicate format only supports single image input. Using first image.")

            # Make request
            res = await self._make_request(url, headers, data)

            # Process response and return result
            return await self._process_response(res)

        except Exception as e:
            print('Error generating image with Replicate:', e)
            traceback.print_exc()
            raise e
