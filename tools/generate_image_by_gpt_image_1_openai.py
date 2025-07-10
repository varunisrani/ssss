#!/usr/bin/env python3
"""
OpenAI GPT-4 Image Generation Tool

This tool generates images using OpenAI's GPT-4 Image model (gpt-image-1) directly
through the OpenAI API, similar to how other OpenAI models like gpt-4o-mini work.
"""

from typing import Optional, Annotated
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.tools.base import InjectedToolCallId
from pydantic import BaseModel, Field
from .utils.image_generation_core import generate_image_with_provider


class GenerateImageByGptImage1OpenAIInputSchema(BaseModel):
    """Input schema for GPT-4 Image generation via OpenAI API"""
    
    prompt: str = Field(description="Text prompt for image generation")
    aspect_ratio: str = Field(
        default="1:1",
        description="Aspect ratio for the image (1:1, 16:9, 9:16, 4:3, 3:4)"
    )
    input_images: Optional[list[str]] = Field(
        default=None,
        description="List of input image paths for editing (optional)"
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("generate_image_by_gpt_image_1_openai",
      description="Generate an image using OpenAI GPT-4 Image model (gpt-image-1) directly via OpenAI API. Use this for direct OpenAI API access without provider wrapper.",
      args_schema=GenerateImageByGptImage1OpenAIInputSchema)
async def generate_image_by_gpt_image_1_openai(
    prompt: str,
    aspect_ratio: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    input_images: list[str] | None = None,
) -> str:
    """
    Generate image using OpenAI GPT-4 Image model (gpt-image-1) directly
    """
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')
    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider='openai',  # Use OpenAI provider directly
        model='gpt-image-1',  # Clean model name without provider prefix
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=input_images,
    )


# Export the tool for easy import
__all__ = ["generate_image_by_gpt_image_1_openai"]