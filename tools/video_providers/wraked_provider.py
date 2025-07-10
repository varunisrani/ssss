import traceback
from typing import Optional, Dict, Any, List
from .video_base_provider import VideoProviderBase
from utils.http_client import HttpClient
from services.config_service import config_service
import httpx


class WrakedVideoProvider(VideoProviderBase, provider_name="wraked"):
    """Wraked Labs Cloud video generation provider implementation"""

    def __init__(self):
        config = config_service.app_config.get('wraked', {})
        self.api_url = str(config.get("url", "")).rstrip("/")
        self.api_token = str(config.get("api_key", ""))

        if not self.api_url:
            raise ValueError("Wraked API URL is not configured")
        if not self.api_token:
            raise ValueError("Wraked API token is not configured")

    def _build_url(self) -> str:
        """Build request URL"""
        if self.api_url.rstrip('/').endswith('/api/v1'):
            return f"{self.api_url.rstrip('/')}/video/generations"
        else:
            return f"{self.api_url.rstrip('/')}/api/v1/video/generations"

    def _build_headers(self) -> dict[str, str]:
        """Build request headers"""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _build_request_payload(
        self,
        prompt: str,
        model: str,
        resolution: str = "480p",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        camera_fixed: bool = True,
        input_images: Optional[List[str]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build request payload for Jaaz Cloud API"""
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "resolution": resolution,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "camera_fixed": camera_fixed,
        }

        if input_images:
            payload["input_images"] = input_images

        return payload

    def _extract_video_url(self, response_data: Dict[str, Any]) -> str:
        """Extract video URL from Jaaz Cloud API response"""
        if "data" not in response_data or not response_data["data"]:
            raise Exception(
                "Video generation failed: No video data in response")

        video_url = response_data["data"][0]["url"]
        print(f"🎥 Jaaz Cloud video URL: {video_url}")
        return video_url

    async def generate(
        self,
        prompt: str,
        model: str,
        resolution: str = "480p",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        input_images: Optional[List[str]] = None,
        camera_fixed: bool = True,
        **kwargs: Any
    ) -> str:
        """
        Generate video using Jaaz Cloud API

        Returns:
            str: Video URL for download
        """
        try:
            url = self._build_url()
            headers = self._build_headers()

            # Build request payload
            data = self._build_request_payload(
                prompt=prompt,
                model=model,
                resolution=resolution,
                duration=duration,
                aspect_ratio=aspect_ratio,
                camera_fixed=camera_fixed,
                input_images=input_images,
                **kwargs
            )

            print(
                f'🎥 Jaaz API request: {url}, model: {data["model"]}, prompt: {data["prompt"]}')

            # Make API request with extended timeout for video generation
            video_timeout = httpx.Timeout(
                connect=20.0,
                read=10 * 60,  # 10 minutes for video generation
                write=30.0,
                pool=60.0
            )

            async with HttpClient.create(timeout=video_timeout) as client:
                response = await client.post(url, headers=headers, json=data)
                print('👇response', url, response.content)
                if response.status_code != 200:
                    try:
                        error_data = response.json() if response.content else {}
                        error_message = error_data.get(
                            "error", f"HTTP {response.status_code}")
                    except Exception as e:
                        # If response is not JSON, use the raw text or status code
                        error_message = f"HTTP {response.status_code} {response.text if response.content else ''}"
                    raise Exception(
                        f'Video generation failed: {error_message}')

                if not response.content:
                    raise Exception(
                        'Video generation failed: Empty response from server')

                # Parse JSON data
                result = response.json()
                print('🎥 Jaaz API response', result)

                # Extract and return video URL
                video_url = self._extract_video_url(result)
                return video_url

        except Exception as e:
            print('Error generating video with Jaaz:', e)
            traceback.print_exc()
            raise e
