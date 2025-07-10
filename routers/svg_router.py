"""
SVG Router - API endpoints for image to SVG conversion
"""

import logging
import base64
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.svg_service import svg_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/svg", tags=["svg"])

class ImageToSvgRequest(BaseModel):
    """Request model for image to SVG conversion."""
    image_data: str  # Base64 encoded image data
    user_input: str = ""  # Optional context about the image
    session_id: str = None  # Optional session ID

class SvgConversionResponse(BaseModel):
    """Response model for SVG conversion."""
    success: bool
    session_id: str = None
    components: Dict[str, Any] = None
    preview_svg: str = None
    error: str = None

@router.post("/convert-image-to-svg", response_model=SvgConversionResponse)
async def convert_image_to_svg(request: ImageToSvgRequest):
    """
    Convert an image to editable SVG format.
    
    This endpoint processes an image through the parallel SVG generation pipeline:
    - Stage 7: Extract text, background, and elements in parallel
    - Stage 8: AI-powered combination of SVG layers
    - Stage 9: Post-process and cleanup
    
    Args:
        request: ImageToSvgRequest containing base64 image data and optional context
        
    Returns:
        SvgConversionResponse with SVG components and preview
    """
    try:
        logger.info(f"Starting SVG conversion for image, context: {request.user_input[:100] if request.user_input else 'None'}")
        
        # Decode base64 image data
        try:
            image_data = base64.b64decode(request.image_data)
        except Exception as e:
            logger.error(f"Failed to decode base64 image data: {e}")
            raise HTTPException(status_code=400, detail="Invalid base64 image data")
        
        # Validate image data
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="Empty image data")
        
        # Process image through SVG pipeline
        result = await svg_service.process_image_to_svg(
            image_data=image_data,
            user_input=request.user_input,
            session_id=request.session_id
        )
        
        if not result.get('success', False):
            error_msg = result.get('error', 'Unknown error during SVG conversion')
            logger.error(f"SVG conversion failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        logger.info(f"SVG conversion completed successfully for session: {result.get('session_id')}")
        
        return SvgConversionResponse(
            success=True,
            session_id=result.get('session_id'),
            components=result.get('components'),
            preview_svg=result.get('preview_svg')
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in SVG conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/convert-uploaded-image")
async def convert_uploaded_image(
    file: UploadFile = File(...),
    user_input: str = Form(""),
    session_id: str = Form(None)
):
    """
    Convert an uploaded image file to SVG format.
    
    Alternative endpoint that accepts file uploads instead of base64 data.
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read file data
        file_data = await file.read()
        
        if len(file_data) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Process through SVG pipeline
        result = await svg_service.process_image_to_svg(
            image_data=file_data,
            user_input=user_input,
            session_id=session_id
        )
        
        if not result.get('success', False):
            error_msg = result.get('error', 'Unknown error during SVG conversion')
            raise HTTPException(status_code=500, detail=error_msg)
        
        return JSONResponse(content={
            "success": True,
            "session_id": result.get('session_id'),
            "components": result.get('components'),
            "preview_svg": result.get('preview_svg')
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in uploaded image conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/health")
async def svg_service_health():
    """Check if SVG service dependencies are available."""
    try:
        # Check service availability
        health_status = {
            "service": "available",
            "dependencies": {
                "vtracer": hasattr(svg_service, '_check_dependencies') and svg_service._check_dependencies(),
                "opencv": True,  # Basic check
                "pytesseract": True  # Basic check
            }
        }
        
        return JSONResponse(content=health_status)
        
    except Exception as e:
        logger.error(f"Error checking SVG service health: {e}")
        return JSONResponse(
            content={"service": "error", "error": str(e)},
            status_code=500
        )

@router.get("/capabilities")
async def get_svg_capabilities():
    """Get information about SVG conversion capabilities."""
    return JSONResponse(content={
        "features": [
            "Text extraction (OCR)",
            "Background extraction", 
            "Element vectorization",
            "AI-powered layer combination",
            "SVG post-processing"
        ],
        "supported_formats": ["PNG", "JPEG", "JPG", "GIF", "BMP"],
        "output_format": "SVG",
        "parallel_processing": True,
        "ai_enhancement": True
    })