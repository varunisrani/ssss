from typing import Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool, InjectedToolCallId  # type: ignore
from langchain_core.runnables import RunnableConfig
from tools.utils.image_generation_core import generate_image_with_provider


class GenerateImageByFlux11ProInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for image generation. If you want to edit an image, please describe what you want to edit in the prompt."
    )
    aspect_ratio: str = Field(
        description="Required. Aspect ratio of the image, only these values are allowed: 1:1, 16:9, 4:3, 3:4, 9:16. Choose the best fitting aspect ratio according to the prompt. Best ratio for posters is 3:4"
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("generate_image_by_flux_1_1_pro",
      description="Generate an image by Flux 1.1 Pro model using text prompt. This model does NOT support input images for reference or editing. Use this model for high-quality image generation with Flux's advanced AI. Supports multiple providers with automatic fallback.",
      args_schema=GenerateImageByFlux11ProInputSchema)
async def generate_image_by_flux_1_1_pro(
    prompt: str,
    aspect_ratio: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    """
    Generate an image using Flux 1.1 Pro model via the provider framework
    """
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')

    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider='wraked',
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        model="black-forest-labs/flux-1.1-pro",
        input_images=None,
    )


# Export the tool for easy import
__all__ = ["generate_image_by_flux_1_1_pro"]
