"""
Simple Image to SVG API - Direct port of InfoUI Stages 7-9
Simple endpoint that takes an image and returns SVG using exact InfoUI stages
"""

import logging
import base64
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.image_to_svg_converter import convert_image_to_svg_stages_7_8_9

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["image-to-svg"])

class ImageToSvgRequest(BaseModel):
    image_data: str  # Base64 encoded image data

class ImageToSvgResponse(BaseModel):
    success: bool
    combined_svg: str = ""
    text_svg: str = ""
    elements_svg: str = ""
    background_base64: str = ""
    error: str = ""

@router.post("/convert-image-to-svg-simple", response_model=ImageToSvgResponse)
async def convert_image_to_svg_simple(request: ImageToSvgRequest):
    """
    Convert image to SVG using exact InfoUI Stages 7-9
    
    Simple endpoint that:
    1. Takes base64 image data
    2. Runs InfoUI Stages 7-9 
    3. Returns combined SVG result
    """
    try:
        logger.info("Starting simple image to SVG conversion")
        
        # Decode base64 image data
        try:
            image_data = base64.b64decode(request.image_data)
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise HTTPException(status_code=400, detail="Invalid base64 image data")
        
        # Convert using InfoUI stages 7-9
        result = convert_image_to_svg_stages_7_8_9(image_data)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Conversion failed'))
        
        return ImageToSvgResponse(
            success=True,
            combined_svg=result['combined_svg'],
            text_svg=result['text_svg'],
            elements_svg=result['elements_svg'],
            background_base64=result['background_base64']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in simple image to SVG conversion: {e}")
        raise HTTPException(status_code=500, detail=str(e))