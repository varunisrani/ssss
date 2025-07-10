from typing import Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool, InjectedToolCallId  # type: ignore
from langchain_core.runnables import RunnableConfig
from tools.utils.image_generation_core import generate_image_with_provider


class GenerateImageByFluxKontextProInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for image generation. If you want to edit an image, please describe what you want to edit in the prompt."
    )
    aspect_ratio: str = Field(
        description="Required. Aspect ratio of the image, only these values are allowed: 1:1, 16:9, 4:3, 3:4, 9:16. Choose the best fitting aspect ratio according to the prompt. Best ratio for posters is 3:4"
    )
    input_image: str | None = Field(
        default=None,
        description="Optional; Image to use as reference. Pass an image_id here, e.g. 'im_jurheut7.png'. Best for image editing cases like: Editing specific parts of the image, Removing specific objects, Maintaining visual elements across scenes (character/object consistency), Generating new content in the style of the reference (style transfer), etc."
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("generate_image_by_flux_kontext_pro_wraked",
      description="Generate an image by Flux Kontext Pro model using text prompt or optionally pass an image for reference or editing. Good for object removal, image editing, etc. Only one input image is allowed.",
      args_schema=GenerateImageByFluxKontextProInputSchema)
async def generate_image_by_flux_kontext_pro_wraked(
    prompt: str,
    aspect_ratio: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    input_image: str | None = None,
) -> str:
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')
    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider='wraked',
        model='black-forest-labs/flux-kontext-pro',
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=[input_image] if input_image else None,
    )

# Export the tool for easy import
__all__ = ["generate_image_by_flux_kontext_pro_wraked"]
