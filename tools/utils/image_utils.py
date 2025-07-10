import os
import aiofiles
from PIL import Image
from io import BytesIO
import base64
from typing import Tuple
from nanoid import generate
from utils.http_client import HttpClient
from services.config_service import FILES_DIR


def generate_image_id() -> str:
    """Generate unique image ID"""
    return generate(size=10)


async def get_image_info_and_save(
    url: str,
    file_path_without_extension: str,
    is_b64: bool = False
) -> Tuple[str, int, int, str]:
    """
    Download image from URL or decode base64, get image info and save to file

    Args:
        url: Image URL or base64 string
        file_path_without_extension: File path without extension
        is_b64: Whether the url is a base64 string

    Returns:
        tuple[str, int, int, str]: (mime_type, width, height, extension)
    """
    try:
        if is_b64:
            image_data = base64.b64decode(url)
        else:
            # Fetch the image asynchronously
            async with HttpClient.create() as client:
                response = await client.get(url)
                # Read the image content as bytes
                image_data = response.content

        # Open image to get info
        image = Image.open(BytesIO(image_data))
        width, height = image.size

        # Determine format and extension
        format_name = image.format or 'PNG'
        extension = format_name.lower()
        if extension == 'jpeg':
            extension = 'jpg'

        # Determine MIME type
        mime_type = f"image/{extension}"
        if extension == 'jpg':
            mime_type = "image/jpeg"

        # Save file
        file_path = f"{file_path_without_extension}.{extension}"
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(image_data)

        return mime_type, width, height, extension

    except Exception as e:
        print(f"Error processing image: {e}")
        raise e


# Canvas-related utilities have been moved to tools/image_generation/image_canvas_utils.py


# Canvas element generation moved to tools/image_generation/image_canvas_utils.py


# Canvas saving functionality moved to tools/image_generation/image_canvas_utils.py


# Image generation orchestration moved to tools/image_generation/image_generation_core.py
# Notification functions moved to tools/image_generation/image_canvas_utils.py


async def process_input_image(input_image: str | None) -> str | None:
    """
    Process input image and convert to base64 format

    Args:
        input_image: Image file path

    Returns:
        Base64 encoded image with data URL, or None if no image
    """
    if not input_image:
        return None

    try:
        full_path = os.path.join(FILES_DIR, input_image)
        if not os.path.exists(full_path):
            print(f"Warning: Image file not found: {full_path}")
            return None

        image = Image.open(full_path)
        ext = os.path.splitext(input_image)[1].lower()
        mime_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'
        }
        mime_type = mime_type_map.get(ext, 'image/jpeg')

        with BytesIO() as output:
            image.save(output, format=str(mime_type.split('/')[1]).upper())
            compressed_data = output.getvalue()
            b64_data = base64.b64encode(compressed_data).decode('utf-8')

        data_url = f"data:{mime_type};base64,{b64_data}"
        return data_url

    except Exception as e:
        print(f"Error processing image {input_image}: {e}")
        return None
