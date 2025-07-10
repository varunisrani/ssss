from typing import Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool, InjectedToolCallId  # type: ignore
from langchain_core.runnables import RunnableConfig
from tools.utils.image_generation_core import generate_image_with_provider

class EditImageByFluxKontextProInputSchema(BaseModel):
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
    output_format: str = Field(
        default="jpg",
        description="Output image format. Options: jpg, png, webp. JPG is recommended for photos, PNG for images with transparency."
    )
    safety_tolerance: int = Field(
        default=2,
        description="Safety tolerance level (1-5). Higher values are more permissive. Recommended: 2"
    )
    prompt_upsampling: bool = Field(
        default=False,
        description="Enable prompt upsampling for enhanced prompt processing. Set to True for more detailed prompt interpretation."
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("edit_image_by_flux_kontext_pro_replicate",
      description="Edit an existing image using Flux Kontext Pro model. This tool can modify images based on text prompts - change colors, add/remove objects, alter backgrounds, modify lighting, etc. Requires an input image and editing instructions. Higher quality than Dev model.",
      args_schema=EditImageByFluxKontextProInputSchema)
async def edit_image_by_flux_kontext_pro_replicate(
    prompt: str,
    input_image: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    aspect_ratio: str = "match_input_image",
    output_format: str = "jpg",
    safety_tolerance: int = 2,
    prompt_upsampling: bool = False,
) -> str:
    """
    Edit an image using Flux Kontext Pro model via the Replicate provider framework
    
    This tool specializes in image editing tasks like:
    - Changing colors and textures
    - Adding or removing objects
    - Modifying backgrounds
    - Adjusting lighting and atmosphere
    - Style transformations
    - Object replacement
    - Professional-grade image modifications
    """
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')

    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider='replicate',
        model="black-forest-labs/flux-kontext-pro",
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=[input_image],
        # Pass editing-specific parameters
        output_format=output_format,
        safety_tolerance=safety_tolerance,
        prompt_upsampling=prompt_upsampling,
    )

# Export the tool for easy import
__all__ = ["edit_image_by_flux_kontext_pro_replicate"]