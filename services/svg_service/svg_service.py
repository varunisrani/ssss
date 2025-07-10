"""
SVG Service - Convert images to editable SVG format
Adapted from InfoUI parallel SVG generation pipeline (Stages 7-9)
"""

import os
import base64
import uuid
import logging
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple, Dict, Any, Optional
from io import BytesIO

# Core dependencies
import numpy as np
from PIL import Image

# SVG and image processing
try:
    import vtracer
    VTRACER_AVAILABLE = True
except ImportError:
    VTRACER_AVAILABLE = False

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

# Jaaz dependencies
from services.config_service import config_service

logger = logging.getLogger(__name__)

class SvgService:
    """Service for converting images to editable SVG format using parallel processing."""
    
    def __init__(self):
        self.session_dir = None
        self._check_dependencies()
    
    def _check_dependencies(self) -> bool:
        """Check if all required dependencies are available."""
        missing = []
        if not VTRACER_AVAILABLE:
            missing.append("vtracer")
        if not OCR_AVAILABLE:
            missing.append("pytesseract")
        if not OPENCV_AVAILABLE:
            missing.append("opencv-python")
        
        if missing:
            logger.warning(f"Missing SVG dependencies: {missing}")
            return False
        return True
    
    async def process_image_to_svg(
        self, 
        image_data: bytes, 
        user_input: str = "",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main pipeline function - Convert image to editable SVG components.
        
        Args:
            image_data: Raw image bytes
            user_input: User description/context for the image
            session_id: Optional session ID for file organization
            
        Returns:
            Dictionary containing SVG components and URLs
        """
        try:
            # Create session for this conversion
            if not session_id:
                session_id = f"svg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            logger.info(f"Starting SVG conversion for session: {session_id}")
            
            # Stage 7: Triple Parallel Processing
            logger.info("Stage 7: Triple Parallel Processing - Text SVG, Background Extraction, and Elements SVG")
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                # Submit all three tasks in parallel
                ocr_future = executor.submit(self._process_ocr_svg, image_data)
                background_future = executor.submit(self._process_background_extraction, image_data)
                elements_future = executor.submit(self._process_clean_svg, image_data)
                
                # Get results
                text_svg_code, text_svg_path = ocr_future.result()
                background_base64, background_filename, background_path = background_future.result()
                elements_svg_code, elements_svg_path, edited_png_path = elements_future.result()
            
            # Stage 8: AI-Powered 3-Layer SVG Combination
            logger.info("Stage 8: AI-Powered 3-Layer SVG Combination")
            combined_svg_code = await self._ai_combine_svgs(
                text_svg_code, 
                elements_svg_code, 
                background_base64,
                user_input
            )
            
            # Stage 9: Post-process SVG
            logger.info("Stage 9: Post-processing SVG to remove artifacts")
            final_svg_code = await self._post_process_svg(combined_svg_code)
            
            # Save final SVG
            final_svg_path = await self._save_svg_to_temp(final_svg_code, "final_combined")
            
            result = {
                "success": True,
                "session_id": session_id,
                "components": {
                    "text_svg": {
                        "code": text_svg_code,
                        "path": text_svg_path
                    },
                    "elements_svg": {
                        "code": elements_svg_code,
                        "path": elements_svg_path
                    },
                    "background": {
                        "base64": background_base64,
                        "path": background_path
                    },
                    "combined_svg": {
                        "code": final_svg_code,
                        "path": final_svg_path
                    }
                },
                "preview_svg": final_svg_code
            }
            
            logger.info(f"SVG conversion completed successfully for session: {session_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error in SVG conversion: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
    
    def _process_ocr_svg(self, image_data: bytes) -> Tuple[str, str]:
        """Stage 7a: Extract text and convert to SVG."""
        try:
            # Convert image data to PIL Image
            image = Image.open(BytesIO(image_data))
            
            if not OCR_AVAILABLE:
                logger.warning("OCR not available, returning empty text SVG")
                return self._create_empty_text_svg(), ""
            
            # Extract text using OCR
            text_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            # Create SVG from text data
            svg_content = self._create_text_svg(text_data, image.size)
            
            # Save to temporary file
            svg_path = self._save_temp_file(svg_content, "text_svg.svg")
            
            return svg_content, svg_path
            
        except Exception as e:
            logger.error(f"Error in OCR SVG processing: {e}")
            return self._create_empty_text_svg(), ""
    
    def _process_background_extraction(self, image_data: bytes) -> Tuple[str, str, str]:
        """Stage 7b: Extract and process background."""
        try:
            # Convert to PIL Image
            image = Image.open(BytesIO(image_data))
            
            # For now, use the original image as background
            # In a full implementation, you would apply background extraction algorithms
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            background_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Save to temporary file
            background_path = self._save_temp_file(buffer.getvalue(), "background.png", is_binary=True)
            filename = os.path.basename(background_path)
            
            return background_base64, filename, background_path
            
        except Exception as e:
            logger.error(f"Error in background extraction: {e}")
            return "", "", ""
    
    def _process_clean_svg(self, image_data: bytes) -> Tuple[str, str, str]:
        """Stage 7c: Extract elements and convert to clean SVG."""
        try:
            if not VTRACER_AVAILABLE:
                logger.warning("VTracer not available, returning simplified SVG")
                return self._create_simple_shapes_svg(image_data)
            
            # Save image to temporary file for VTracer
            temp_image_path = self._save_temp_file(image_data, "input_image.png", is_binary=True)
            
            # Use VTracer to convert to SVG
            svg_content = vtracer.convert_image_to_svg_py(
                temp_image_path,
                colormode='color',
                hierarchical='stacked',
                mode='polygon',
                filter_speckle=4,
                color_precision=6,
                layer_difference=16,
                corner_threshold=60,
                length_threshold=4.0,
                splice_threshold=45,
                path_precision=3
            )
            
            # Save SVG
            svg_path = self._save_temp_file(svg_content, "elements.svg")
            
            # Also create a cleaned PNG version
            png_path = self._save_temp_file(image_data, "elements_clean.png", is_binary=True)
            
            return svg_content, svg_path, png_path
            
        except Exception as e:
            logger.error(f"Error in clean SVG processing: {e}")
            return self._create_simple_shapes_svg(image_data)
    
    async def _ai_combine_svgs(
        self, 
        text_svg: str, 
        elements_svg: str, 
        background_base64: str,
        user_context: str = ""
    ) -> str:
        """Stage 8: AI-powered combination of SVG layers."""
        try:
            # Get OpenAI API key from config
            config = config_service.get_config()
            api_key = config.get('openai', {}).get('api_key', '')
            
            if not api_key:
                logger.warning("No OpenAI API key found, using fallback combination")
                return self._fallback_combine_svgs(text_svg, elements_svg, background_base64)
            
            # Create AI prompt for SVG combination
            system_prompt = """You are an expert SVG designer. Combine the provided SVG elements into a single, well-structured SVG.

Requirements:
1. Preserve all visual elements from both input SVGs
2. Ensure proper layering (background, elements, text on top)
3. Maintain proper SVG structure with viewBox
4. Optimize for editability
5. Remove any duplicate or conflicting elements
6. Ensure all paths and shapes are properly closed

Return only the complete, valid SVG code."""
            
            user_prompt = f"""Combine these SVG components into a single editable SVG:

Text Layer:
{text_svg}

Elements Layer:
{elements_svg}

Context: {user_context}

Create a clean, editable SVG that combines these layers properly."""
            
            # Make AI API call (simplified - you would use the actual OpenAI client here)
            combined_svg = await self._call_openai_for_svg(system_prompt, user_prompt)
            
            if combined_svg and combined_svg.strip():
                return combined_svg
            else:
                return self._fallback_combine_svgs(text_svg, elements_svg, background_base64)
                
        except Exception as e:
            logger.error(f"Error in AI SVG combination: {e}")
            return self._fallback_combine_svgs(text_svg, elements_svg, background_base64)
    
    async def _post_process_svg(self, svg_code: str) -> str:
        """Stage 9: Post-process SVG to clean up artifacts."""
        try:
            # Basic cleanup - remove empty elements, fix structure
            lines = svg_code.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('<!--'):
                    continue
                # Remove empty paths
                if '<path d=""' in line or '<path d=\'\'' in line:
                    continue
                cleaned_lines.append(line)
            
            return '\n'.join(cleaned_lines)
            
        except Exception as e:
            logger.error(f"Error in SVG post-processing: {e}")
            return svg_code
    
    # Helper methods
    
    def _create_empty_text_svg(self) -> str:
        """Create an empty text SVG placeholder."""
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">
    <!-- Text layer - empty -->
</svg>'''
    
    def _create_text_svg(self, text_data: dict, image_size: tuple) -> str:
        """Create SVG from OCR text data."""
        width, height = image_size
        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">
    <g id="text-layer">'''
        
        # Process OCR data to create text elements
        for i, text in enumerate(text_data.get('text', [])):
            if text.strip():
                x = text_data['left'][i]
                y = text_data['top'][i]
                w = text_data['width'][i]
                h = text_data['height'][i]
                
                svg_content += f'''
        <text x="{x}" y="{y + h}" font-size="{h * 0.8}" fill="black">{text}</text>'''
        
        svg_content += '''
    </g>
</svg>'''
        return svg_content
    
    def _create_simple_shapes_svg(self, image_data: bytes) -> Tuple[str, str, str]:
        """Create a simplified SVG when VTracer is not available."""
        try:
            image = Image.open(BytesIO(image_data))
            width, height = image.size
            
            # Create a simple rectangular placeholder
            svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">
    <g id="elements-layer">
        <rect x="10" y="10" width="{width-20}" height="{height-20}" 
              fill="none" stroke="black" stroke-width="2"/>
        <text x="{width//2}" y="{height//2}" text-anchor="middle" 
              font-size="16" fill="black">Simplified SVG - Install VTracer for full conversion</text>
    </g>
</svg>'''
            
            svg_path = self._save_temp_file(svg_content, "simple_elements.svg")
            png_path = self._save_temp_file(image_data, "simple_elements.png", is_binary=True)
            
            return svg_content, svg_path, png_path
            
        except Exception as e:
            logger.error(f"Error creating simple SVG: {e}")
            return "", "", ""
    
    def _fallback_combine_svgs(self, text_svg: str, elements_svg: str, background_base64: str) -> str:
        """Fallback method to combine SVGs without AI."""
        # Extract viewBox from elements SVG
        viewbox = 'viewBox="0 0 400 300"'  # default
        
        if 'viewBox=' in elements_svg:
            import re
            match = re.search(r'viewBox="[^"]*"', elements_svg)
            if match:
                viewbox = match.group()
        
        # Create combined SVG
        combined = f'''<svg xmlns="http://www.w3.org/2000/svg" {viewbox}>
    <defs>
        <style>
            .text-layer {{ font-family: Arial, sans-serif; }}
            .elements-layer {{ }}
        </style>
    </defs>
    
    <!-- Background Layer -->
    <image href="data:image/png;base64,{background_base64}" width="100%" height="100%" opacity="0.3"/>
    
    <!-- Elements Layer -->
    <g class="elements-layer">
        {self._extract_svg_content(elements_svg)}
    </g>
    
    <!-- Text Layer -->
    <g class="text-layer">
        {self._extract_svg_content(text_svg)}
    </g>
</svg>'''
        
        return combined
    
    def _extract_svg_content(self, svg_code: str) -> str:
        """Extract the inner content of an SVG (between svg tags)."""
        try:
            start = svg_code.find('>')
            end = svg_code.rfind('</svg>')
            if start != -1 and end != -1:
                return svg_code[start + 1:end].strip()
        except:
            pass
        return ""
    
    def _save_temp_file(self, content, filename: str, is_binary: bool = False) -> str:
        """Save content to a temporary file."""
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"jaaz_svg_{uuid.uuid4().hex[:8]}_{filename}")
        
        mode = 'wb' if is_binary else 'w'
        encoding = None if is_binary else 'utf-8'
        
        with open(file_path, mode, encoding=encoding) as f:
            if isinstance(content, str) and is_binary:
                content = content.encode('utf-8')
            f.write(content)
        
        return file_path
    
    async def _save_svg_to_temp(self, svg_content: str, prefix: str) -> str:
        """Save SVG content to temporary file."""
        return self._save_temp_file(svg_content, f"{prefix}.svg")
    
    async def _call_openai_for_svg(self, system_prompt: str, user_prompt: str) -> str:
        """Make API call to OpenAI for SVG processing."""
        # This would integrate with Jaaz's existing OpenAI client
        # For now, return empty string to trigger fallback
        logger.info("AI SVG combination not implemented yet, using fallback")
        return ""

# Global instance
svg_service = SvgService()