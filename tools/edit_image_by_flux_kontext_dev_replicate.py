from typing import Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool, InjectedToolCallId  # type: ignore
from langchain_core.runnables import RunnableConfig
from tools.utils.image_generation_core import generate_image_with_provider

class EditImageByFluxKontextDevInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. Editing instructions for the image (e.g., 'Change the car color to red, turn the headlights on', 'Remove the person from the background', 'Add a sunset sky'). Be specific about what changes you want to make."
    )
    input_image: str = Field(
        description="Required. Image to edit. Pass an image_id here, e.g. 'im_jurheut7.png'. This is the source image that will be modified according to the prompt."
    )
    aspect_ratio: str = Field(
        default="match_input_image",
        description="Aspect ratio for the edited image. Use 'match_input_image' to keep the same aspect ratio as the input image, or specify: 1:1, 16:9, 4:3, 3:4, 9:16"
    )
    go_fast: bool = Field(
        default=True,
        description="Enable fast mode for quicker editing. Set to True for faster results, False for higher quality (slower)."
    )
    guidance: float = Field(
        default=2.5,
        description="Guidance scale for editing strength (1.0-10.0). Higher values make the model follow the prompt more closely. Recommended: 2.5"
    )
    output_format: str = Field(
        default="jpg",
        description="Output image format. Options: jpg, png, webp. JPG is recommended for photos, PNG for images with transparency."
    )
    output_quality: int = Field(
        default=80,
        description="Output image quality (1-100). Higher values = better quality but larger file size. Recommended: 80"
    )
    num_inference_steps: int = Field(
        default=30,
        description="Number of inference steps (10-50). More steps = better quality but slower generation. Recommended: 30"
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("edit_image_by_flux_kontext_dev_replicate",
      description="Edit an existing image using Flux Kontext Dev model. This tool can modify images based on text prompts - change colors, add/remove objects, alter backgrounds, modify lighting, etc. Requires an input image and editing instructions.",
      args_schema=EditImageByFluxKontextDevInputSchema)
async def edit_image_by_flux_kontext_dev_replicate(
    prompt: str,
    input_image: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    aspect_ratio: str = "match_input_image",
    go_fast: bool = True,
    guidance: float = 2.5,
    output_format: str = "jpg",
    output_quality: int = 80,
    num_inference_steps: int = 30,
) -> str:
    """
    Edit an image using Flux Kontext Dev model via the Replicate provider framework
    
    This tool specializes in image editing tasks like:
    - Changing colors and textures
    - Adding or removing objects
    - Modifying backgrounds
    - Adjusting lighting and atmosphere
    - Style transformations
    - Object replacement
    """
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')

    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider='replicate',
        model="black-forest-labs/flux-kontext-dev",
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=[input_image],
        # Pass editing-specific parameters
        go_fast=go_fast,
        guidance=guidance,
        output_format=output_format,
        output_quality=output_quality,
        num_inference_steps=num_inference_steps,
    )

# Export the tool for easy import
__all__ = ["edit_image_by_flux_kontext_dev_replicate"]