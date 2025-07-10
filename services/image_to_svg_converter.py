from flask import Flask, request, jsonify, send_from_directory
import os
import requests
import json
import logging
from flask_cors import CORS
import re
import base64
from io import BytesIO
import cairosvg
from PIL import Image
import openai
import uuid
from datetime import datetime
from dotenv import load_dotenv
import vtracer  # VTracer for image-to-SVG conversion
import asyncio
import aiohttp
from functools import lru_cache
import hashlib
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import cv2
from PIL import Image, ImageOps
import numpy as np
import replicate  # Added for Flux image generation

# Load environment variables
load_dotenv()

# Set up Replicate API token from environment
import os
replicate_key = os.getenv('REPLICATE_API_KEY')
if replicate_key:
    os.environ['REPLICATE_API_TOKEN'] = replicate_key

app = Flask(__name__)

# Configure CORS with specific settings
CORS(app, 
     origins=[
         'http://localhost:3000', 
         'http://localhost:3001',
        'http://localhost:3002',
         'http://127.0.0.1:3000', 
         'http://127.0.0.1:3001',
         'https://pppp-351z.onrender.com',
         'https://infoui.vercel.app',
         'https://infoui.vercel.app/'
     ],
     methods=['GET', 'POST', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization'],
     supports_credentials=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Conditional import of modules that may have additional dependencies
try:
    from . import remove_text_simple  # Text removal for image preprocessing
    REMOVE_TEXT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"remove_text_simple not available: {e}")
    REMOVE_TEXT_AVAILABLE = False

try:
    from . import png_to_svg_converter  # PNG to SVG converter utilities
    PNG_CONVERTER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"png_to_svg_converter not available: {e}")
    PNG_CONVERTER_AVAILABLE = False

# Custom logging filter to suppress 404 errors for missing image files
class ImageNotFoundFilter(logging.Filter):
    def filter(self, record):
        # Suppress 404 logs for missing image files
        try:
            log_message = str(record.getMessage()) if hasattr(record, 'getMessage') else str(record.msg)
            
            # Check if this is a 404 request for image files
            if ('404' in log_message and 
                ('/static/images/' in log_message or 
                 'background_' in log_message or 
                 '.png HTTP/1.1' in log_message or 
                 '.jpg HTTP/1.1' in log_message or 
                 '.svg HTTP/1.1' in log_message)):
                return False
        except:
            pass
        return True

# Apply the filter to suppress image 404 logs from werkzeug (Flask's request logger)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addFilter(ImageNotFoundFilter())
werkzeug_logger.setLevel(logging.WARNING)  # Only show warnings and errors, not INFO

# Directory setup - store all files in main server static folder
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')
IMAGES_DIR = os.path.join(STATIC_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

# Public URL configuration for deployed environment
def get_public_base_url():
    """Get the public base URL for serving images"""
    # Check if we're in production (Render deployment)
    if os.getenv('PORT'):
        # Production environment - use the deployed URL
        return 'https://pppp-351z.onrender.com'
    else:
        # Local development environment
        return 'http://localhost:5000'

def get_public_image_url(relative_path):
    """Convert relative image path to public URL"""
    base_url = get_public_base_url()
    # Ensure the path starts with /static/images/
    if not relative_path.startswith('/static/images/'):
        if relative_path.startswith('static/images/'):
            relative_path = '/' + relative_path
        elif relative_path.startswith('sessions/'):
            relative_path = '/static/images/' + relative_path
        else:
            relative_path = '/static/images/' + relative_path
    
    return f"{base_url}{relative_path}"

# API keys
OPENAI_API_KEY_ENHANCER = os.getenv('OPENAI_API_KEY_ENHANCER')
OPENAI_API_KEY_SVG = os.getenv('OPENAI_API_KEY_SVG')

if not OPENAI_API_KEY_ENHANCER or not OPENAI_API_KEY_SVG:
    raise ValueError("OpenAI API keys must be set in environment variables")

# OpenAI client setupkk
openai.api_key = OPENAI_API_KEY_SVG

# OpenAI API Endpoints
OPENAI_API_BASE = "https://api.openai.com/v1"
OPENAI_CHAT_ENDPOINT = f"{OPENAI_API_BASE}/chat/completions"

# Model names - updated to use Replicate Flux instead of GPT Image-1
PLANNER_MODEL = "gpt-4o-mini"
DESIGN_KNOWLEDGE_MODEL = "gpt-4o-mini"
PRE_ENHANCER_MODEL = "gpt-4o-mini"
PROMPT_ENHANCER_MODEL = "gpt-4o-mini"
# GPT_IMAGE_MODEL = "gpt-image-1"  # Removed
FLUX_MODEL = "black-forest-labs/flux-kontext-dev"  # Added Replicate Flux model
SVG_GENERATOR_MODEL = "gpt-4o-mini"
CHAT_ASSISTANT_MODEL = "gpt-4o-mini"

# Add parallel SVG processing imports
from concurrent.futures import ThreadPoolExecutor
import pytesseract
import numpy as np

# VTracer and related features availability check
try:
    # Test if vtracer is functional by checking its main function
    vtracer.convert_image_to_svg_py
    VTRACER_AVAILABLE = True
    logger.info("✅ VTracer is available and functional")
except (ImportError, AttributeError) as e:
    logger.warning(f"⚠️ VTracer not available: {e}")
    VTRACER_AVAILABLE = False

# Check overall parallel features availability
PARALLEL_FEATURES_AVAILABLE = VTRACER_AVAILABLE and REMOVE_TEXT_AVAILABLE
if PARALLEL_FEATURES_AVAILABLE:
    logger.info("🎉 Full parallel SVG features are available (VTracer + text removal)")
elif VTRACER_AVAILABLE:
    logger.info("⚡ Basic VTracer functionality is available (without text removal)")
else:
    logger.warning("❌ VTracer functionality is not available")

# Unified storage directory - ALL files go here in organized sessions
UNIFIED_STORAGE_DIR = os.path.join(IMAGES_DIR, 'sessions')
os.makedirs(UNIFIED_STORAGE_DIR, exist_ok=True)

# Legacy parallel directory (kept for backward compatibility)
PARALLEL_OUTPUTS_DIR = os.path.join(IMAGES_DIR, 'parallel')
os.makedirs(PARALLEL_OUTPUTS_DIR, exist_ok=True)

def analyze_background_with_gpt4o_mini(image_base64: str) -> str:
    """Use GPT-4o-mini to analyze image and generate detailed background extraction prompt"""
    logger.info("🧠 Analyzing image with GPT-4o-mini to generate optimal background extraction prompt...")
    
    system_prompt = """🧠 System Prompt for Background Extraction AI
You are a highly skilled image analysis AI specialized in background extraction.

Your job is to analyze the provided image and generate a clear, detailed, and precise prompt for an image editing model to extract ONLY the background.

You must:
- Identify all foreground elements (text, shapes, objects, graphics, logos, icons, overlays, decorative elements)
- Refer to visual elements by their position, color, and appearance (e.g., "centered black text", "red circular logo in top-right")
- Clearly specify what to remove (all foreground elements) vs what to keep (only background colors, gradients, textures)
- Include expected output details (clean background, no foreground elements)
- Use professional and concise formatting
- Never assume or hallucinate any elements not visible in the image

🧾 Input Format:
User Request: "Extract clean background from this image, removing all foreground elements"
Image Reference: An image (PNG, JPG, etc.)

✅ Output Format:
🎯 Background Extraction Prompt

🖼️ Image Analysis: [Brief description of what you see]

---

✂️ Objective:
Extract only the pure background, removing all foreground elements completely.

---

🔍 Foreground Elements to Remove:

1. [Element 1 description – include position, color, shape, text content]
2. [Element 2 description...]
...

---

✅ Background Elements to Keep:
[Describe the background colors, gradients, patterns, textures that should remain]

---

🧼 Output Requirements:
- Background: Keep only base colors, gradients, and textures
- Remove: All text, shapes, objects, graphics, decorative elements
- Result: Clean, empty background surface
- Format: JPG with smooth, seamless areas where elements were removed

---

Return ONLY the extraction prompt for the image editing model, not the analysis format."""

    user_prompt = """Analyze this image and generate a detailed prompt for background extraction.

User Request: Extract clean background from this image, removing all foreground elements (text, shapes, objects, graphics, logos, decorative elements). Keep only the pure background colors, gradients, and textures.

Generate a precise prompt that will instruct an image editing AI to remove all foreground elements and keep only the clean background."""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        analysis_result = response.choices[0].message.content.strip()
        logger.info("✅ GPT-4o-mini analysis completed successfully")
        return analysis_result
        
    except Exception as e:
        logger.error(f"❌ GPT-4o-mini analysis failed: {str(e)}")
        # Fallback to comprehensive prompt
        return "Remove absolutely everything from this image - all text, all shapes, all objects, all elements, all graphics, all icons, all symbols, all overlays, all decorative elements, all geometric shapes, all drawings, all illustrations, all logos, all patterns that are not part of the base background. Keep ONLY the pure background colors, gradients, textures and base patterns. The result should be a completely clean background with no visible elements, shapes, text, or objects of any kind whatsoever. Just the background surface."

def enhance_prompt_for_flux_image(user_prompt, design_context=None):
    """Single optimized prompt enhancement for Flux based on 2024 best practices"""
    logger.info(f"Enhancing prompt for Flux: {user_prompt[:100]}...")
    
    url = OPENAI_CHAT_ENDPOINT
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {OPENAI_API_KEY_ENHANCER}"
    }

    # Create optimized system prompt based on Flux image generation best practices
    system_prompt = """You are an expert Flux prompt enhancement specialist. Your role is to transform basic user image requests into sophisticated, optimized prompts that produce professional, "next-level" image outputs.

IMPORTANT: For this task, avoid using gradient shapes or elements with gradients. Use clear, structured, and solid shapes with strong contrast. Avoid shapes or elements that have similar shades or colors as the background, as these are difficult for vectorization tools like VTracer to identify. All main elements should be visually distinct from the background and from each other, with no subtle gradients or blending. Use flat, solid colors for all shapes and ensure good separation between elements and background.

Core Enhancement Methodology
Transform user inputs using this proven structure:
[Core Subject] + [Setting/Environment] + [Style/Artistic Direction] + [Lighting/Mood] + [Technical Details] + [Composition/Perspective]
Key Principles:

Use natural, conversational language (NOT keyword lists)
Aim for 30-50 words for optimal results
Include rich contextual details and environmental descriptions
Leverage DALL-E 3's synthetic captioning strengths
Focus on complete sentences and narrative descriptions

Enhancement Framework
1. Quality Enhancement Keywords (integrate naturally):

Technical: "highly detailed," "professional photography," "studio quality," "award-winning"
Artistic: "trending on ArtStation," "masterpiece," "hyperrealistic," "cinematic"
Photographic: "shallow depth of field," "perfect composition," "professional lighting"

2. Lighting Enhancement (choose appropriate):

Dramatic: "cinematic lighting," "dramatic shadows," "rim lighting"
Professional: "studio lighting," "soft diffused light," "key lighting"
Atmospheric: "golden hour," "ethereal glow," "moody lighting"
Natural: "natural daylight," "window light," "ambient lighting"

3. Composition Control:

Camera Angles: eye level, bird's eye view, low angle, high angle
Shot Types: close-up, medium shot, wide shot, extreme close-up
Technical Specs: 85mm portrait lens, 24mm wide-angle, f/1.4 aperture

4. Style Direction (match to purpose):

Corporate/Professional: "clean modern design," "minimalist style," "professional aesthetic"
Marketing: "vibrant colors," "eye-catching design," "commercial photography style"
Artistic: "oil painting style," "digital art," "watercolor technique"

Specialized Enhancement Rules
POSTERS (Coming Soon, Events, Marketing):
Formula: "Professional [poster type] featuring [main element], [style description], [color scheme], [mood/atmosphere], [technical quality], [composition notes]"

Enhancement Focus:
- Clear hierarchy and focal points
- Bold, readable typography integration
- Brand-appropriate color schemes
- Marketing-optimized composition
- High-impact visual elements

Example Enhancement:
User: "coming soon poster"
Enhanced: "Professional 'Coming Soon' marketing poster featuring bold typography and anticipation-building imagery, modern minimalist design with vibrant brand colors, dramatic lighting creating excitement, studio-quality commercial photography style, centered composition with clear visual hierarchy."
LOGOS (Brand Identity, Business):
Formula: "Flat vector logo design for [business type], [design elements], [color scheme], [style notes], scalable vector format"

Enhancement Focus:
- Emphasize "flat vector design" and "scalable"
- Minimalist, clean aesthetics
- Professional color schemes
- Clear symbolic representation
- Timeless design principles

Example Enhancement:
User: "tech startup logo"
Enhanced: "Flat vector logo design for innovative tech startup, featuring abstract geometric symbol representing growth and connectivity, modern blue and silver color palette, minimalist professional style with clean lines, scalable vector format suitable for all applications."
TESTIMONIALS (Reviews, Social Proof):
Formula: "Professional testimonial graphic featuring [layout description], [trust elements], [design style], [color scheme], [quality specifications]"

Enhancement Focus:
- Trust-building visual elements
- Clean, readable layouts
- Professional photography style
- Space for customer photos and quotes
- Platform-optimized dimensions

Example Enhancement:
User: "customer testimonial"
Enhanced: "Professional testimonial graphic featuring clean modern layout with space for customer photo and quote text, trust-building design elements including star ratings, soft professional lighting, corporate blue and white color scheme, high-quality marketing material style."
Advanced Enhancement Techniques
Conversational Prompting:

Transform keywords into natural descriptions
Add environmental context and relationships
Include emotional and atmospheric details
Specify material textures and surface qualities

Mood-First Enhancement:

Start with emotional tone and atmosphere
Build subject details around mood
Include sensory descriptions
Add temporal and seasonal context

Technical Optimization:

Specify appropriate aspect ratios (square for social, landscape for banners, portrait for posters)
Include style settings guidance (vivid for marketing, natural for professional)
Add resolution and quality specifications
Mention lighting setup and camera techniques

Output Format
Always provide:

Enhanced Prompt: The complete, optimized prompt (30-50 words)
Key Enhancements: Brief explanation of major improvements made
Technical Notes: Any specific settings or considerations for best results
Alternative Version: A second variation with different style/mood (if helpful)

Quality Checklist
Before finalizing each enhancement, verify:

✅ Uses natural, conversational language
✅ Includes complete environmental context
✅ Incorporates appropriate quality keywords
✅ Specifies lighting and mood clearly
✅ Matches optimal word count (30-50 words)
✅ Optimized for specific image type/purpose
✅ Includes technical and composition details
✅ Maintains user's core intent while maximizing quality

Important Notes

Focus on rich contextual descriptions rather than keyword lists
Leverage DALL-E 3's strength in understanding relationships and environments
Always maintain the user's original intent while dramatically improving specificity
Consider the final use case (social media, print, web, branding) in enhancement decisions
Remember that DALL-E 3 excels with complete scene descriptions including background elements

Transform every basic request into a sophisticated prompt that unlocks DALL-E 3's full potential for professional, next-level image generation."""

    payload = {
        "model": "gpt-4.1-mini",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f" {user_prompt}"
            }
        ],
        "temperature": 0.8,
        "max_tokens": 1000
    }

    try:
        logger.info("Calling OpenAI Chat API for optimized prompt enhancement")
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()

        if response.status_code != 200:
            logger.error(f"OpenAI API error: {response_data}")
            return user_prompt

        enhanced_prompt = response_data["choices"][0]["message"]["content"]
        logger.info(f"Successfully enhanced prompt. Result: {enhanced_prompt[:100]}...")
        return enhanced_prompt

    except Exception as e:
        logger.error(f"Error enhancing prompt: {str(e)}")
        return user_prompt

def generate_image_with_flux(enhanced_prompt, design_context=None, input_image_data=None):
    """Generate image using Replicate Flux model"""
    try:
        logger.info("Generating image with Replicate Flux")
        logger.info(f"Using prompt: {enhanced_prompt[:200]}...")

        # Prepare input parameters
        flux_input = {
            "prompt": enhanced_prompt,
            "go_fast": True,
            "guidance": 2.5,
            "output_format": "jpg",
            "output_quality": 80,
            "num_inference_steps": 30
        }
        
        # Add input image if provided, otherwise use text-to-image mode
        if input_image_data:
            input_image_base64 = base64.b64encode(input_image_data).decode('utf-8')
            input_image_data_url = f"data:image/png;base64,{input_image_base64}"
            flux_input["input_image"] = input_image_data_url
            flux_input["aspect_ratio"] = "match_input_image"
        else:
            flux_input["aspect_ratio"] = "1:1"

        output = replicate.run(FLUX_MODEL, input=flux_input)
        
        # The output is a URL, download the image and convert to base64
        image_url = output[0] if isinstance(output, list) else output
        response = requests.get(image_url)
        image_base64 = base64.b64encode(response.content).decode('utf-8')

        # Create session ID for this generation
        session_id = f"svg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Save the generated image
        filename, relative_path, _ = save_image(image_base64, prefix="flux_image", session_id=session_id)
        
        # Create public URL for the image
        public_url = get_public_image_url(relative_path)

        logger.info("Image generated and saved successfully with Replicate Flux")
        logger.info(f"Public URL created: {public_url}")
        return image_base64, relative_path, public_url
    except Exception as e:
        logger.error(f"Error generating image with Replicate Flux: {str(e)}")
        raise

def generate_svg_from_image(image_base64, enhanced_prompt, use_preprocessing=False):
    """Generate SVG code from image using VTracer with optimized processing"""
    logger.info(f"SVG generation from image using VTracer")
    logger.info(f"Enhanced prompt provided: {enhanced_prompt[:100]}...")
    logger.info(f"Image data size: {len(image_base64)} characters")
    logger.info(f"Preprocessing enabled: {use_preprocessing}")
    
    if not VTRACER_AVAILABLE:
        logger.error("VTracer not available - missing core dependency")
        raise NotImplementedError("VTracer not available - missing core dependency. Please install vtracer.")
    
    try:
        # Decode base64 image data
        image_data = base64.b64decode(image_base64)
        
        # Create session for this conversion
        session_id = f"vtracer_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Save the original image bytes to a temporary PNG file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_input_path = f"temp_input_{timestamp}_{uuid.uuid4()}.png"
        
        with open(temp_input_path, "wb") as f:
            f.write(image_data)
        
        logger.info(f"Saved temporary image: {temp_input_path}")
        
        # Optional preprocessing for better VTracer results
        processing_path = temp_input_path
        if use_preprocessing:
            try:
                logger.info("Applying VTracer preprocessing...")
                processing_path = preprocess_for_vtracer(temp_input_path)
                logger.info(f"Preprocessing completed: {processing_path}")
            except Exception as e:
                logger.warning(f"Preprocessing failed, using original image: {str(e)}")
                processing_path = temp_input_path
        
        # Convert the image to SVG using vtracer with improved settings
        svg_filename, svg_relative_path, _ = save_svg("", prefix="vtracer_svg", session_id=session_id)
        output_svg_path = os.path.join(IMAGES_DIR, svg_relative_path)
        
        logger.info("Converting image to SVG using VTracer with high detail settings...")
        vtracer.convert_image_to_svg_py(
            processing_path,
            output_svg_path,
            # Clustering settings
            colormode='color',         # Color mode (not B/W)
            hierarchical='stacked',    # Stacked mode for layering
            
            # Filter settings
            filter_speckle=1,         # Less filtering, keep more small elements
            
            # Color and precision settings
            color_precision=3,        # More color detail
            layer_difference=16,      # More layers
            
            # Curve fitting settings
            mode='spline',            # Smooth curves
            corner_threshold=30,      # More corners
            length_threshold=1.0,     # Keep short paths
            splice_threshold=20,      # Less aggressive merging
            
            # Additional optimization settings
            max_iterations=20,        # More refinement
            path_precision=2          # Higher precision
        )
        
        # Read the generated SVG content
        with open(output_svg_path, 'r', encoding='utf-8') as f:
            svg_code = f.read()
        
        # Clean up temporary files
        cleanup_files = [temp_input_path]
        if use_preprocessing and processing_path != temp_input_path:
            cleanup_files.append(processing_path)
            
        for file_path in cleanup_files:
            if os.path.exists(file_path):
                os.remove(file_path)
        
        logger.info(f"VTracer SVG generation completed successfully")
        logger.info(f"Generated SVG size: {len(svg_code)} characters")
        logger.info(f"SVG saved to session: {session_id}")
        
        return svg_code
        
    except Exception as e:
        # Clean up temporary files on error
        cleanup_files = []
        if 'temp_input_path' in locals() and os.path.exists(temp_input_path):
            cleanup_files.append(temp_input_path)
        if 'processing_path' in locals() and processing_path != temp_input_path and os.path.exists(processing_path):
            cleanup_files.append(processing_path)
            
        for file_path in cleanup_files:
            try:
                os.remove(file_path)
            except:
                pass
        
        logger.error(f"Error in VTracer SVG generation: {str(e)}")
        raise Exception(f"VTracer SVG generation failed: {str(e)}")

def clean_svg_code_original(svg_code):
    """Original clean and validate SVG code function"""
    try:
        from xml.dom.minidom import parseString
        from xml.parsers.expat import ExpatError
        
        # Parse and clean the SVG
        try:
            doc = parseString(svg_code)
            
            # Get the SVG element
            svg_element = doc.documentElement
            
            # Ensure viewBox exists (minimal changes from original)
            if not svg_element.hasAttribute('viewBox'):
                svg_element.setAttribute('viewBox', '0 0 1080 1080')
            
            # Convert back to string with pretty printing
            cleaned_svg = doc.toxml()
            logger.info("SVG cleaned successfully")
            return cleaned_svg
            
        except ExpatError:
            logger.error("Failed to parse SVG, returning original")
            return svg_code
            
    except Exception as error:
        logger.error(f"Error cleaning SVG: {str(error)}")
        return svg_code

def save_image(image_data, prefix="img", format="PNG", session_id=None):
    """Save image data to subfolder with unique session ID"""
    try:
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{prefix}_{timestamp}_{unique_id}.{format.lower()}"
        
        # Create session ID if not provided
        if not session_id:
            session_id = f"session_{timestamp}_{uuid.uuid4().hex[:8]}"
        
        # Create session subfolder in static/images/
        session_folder = os.path.join(IMAGES_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)
        filepath = os.path.join(session_folder, filename)

        # Convert base64 to image and save
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        image.save(filepath, format=format)
        
        # Return relative path from IMAGES_DIR
        relative_path = f"{session_id}/{filename}"
        logger.info(f"✅ Image saved successfully: {filename} in {session_folder}")
        return filename, relative_path, session_id
    except Exception as e:
        logger.error(f"Error saving image: {str(e)}")
        raise

def save_svg(svg_code, prefix="svg", session_id=None):
    """Save SVG code to subfolder with unique session ID"""
    try:
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{prefix}_{timestamp}_{unique_id}.svg"
        
        # Create session ID if not provided
        if not session_id:
            session_id = f"session_{timestamp}_{uuid.uuid4().hex[:8]}"
        
        # Create session subfolder in static/images/
        session_folder = os.path.join(IMAGES_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)
        filepath = os.path.join(session_folder, filename)

        # Save SVG code to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(svg_code)
        
        # Return relative path from IMAGES_DIR
        relative_path = f"{session_id}/{filename}"
        logger.info(f"✅ SVG saved successfully: {filename} in {session_folder}")
        return filename, relative_path, session_id
    except Exception as e:
        logger.error(f"Error saving SVG: {str(e)}")
        raise

def convert_svg_to_png(svg_code):
    """Convert SVG code to PNG and save both files"""
    try:
        # Save SVG file
        svg_filename, svg_relative_path, session_id = save_svg(svg_code)
        
        # Convert to PNG using cairosvg
        png_data = cairosvg.svg2png(bytestring=svg_code.encode('utf-8'))
        
        # Save PNG file in the same session as SVG
        png_filename, png_relative_path, _ = save_image(
            base64.b64encode(png_data).decode('utf-8'),
            prefix="converted_svg",
            format="PNG",
            session_id=session_id
        )
        
        return svg_relative_path, png_relative_path
    except Exception as e:
        logger.error(f"Error in SVG to PNG conversion: {str(e)}")
        raise

@app.route('/static/images/<path:filename>')
def serve_image(filename):
    """Serve images from the images directory with subfolder support"""
    # Handle both direct files and files in subfolders
    filepath = os.path.join(IMAGES_DIR, filename)
    
    # Security check - ensure the path is within IMAGES_DIR
    if not os.path.abspath(filepath).startswith(os.path.abspath(IMAGES_DIR)):
        return "Access denied", 403
    
    # Extract directory and filename
    directory = os.path.dirname(filepath)
    basename = os.path.basename(filepath)
    
    return send_from_directory(directory, basename)

@app.route('/static/images/parallel/<path:session_folder>/<path:filename>')
def serve_parallel_image(session_folder, filename):
    """Serve images from the parallel pipeline directory (legacy)"""
    parallel_path = os.path.join(PARALLEL_OUTPUTS_DIR, session_folder)
    return send_from_directory(parallel_path, filename)

@app.route('/static/images/sessions/<path:session_id>/<path:filename>')
def serve_session_file(session_id, filename):
    """Serve files from the unified sessions directory"""
    # Security check - ensure the path is within UNIFIED_STORAGE_DIR
    session_path = os.path.join(UNIFIED_STORAGE_DIR, session_id)
    if not os.path.abspath(session_path).startswith(os.path.abspath(UNIFIED_STORAGE_DIR)):
        return "Access denied", 403
    
    return send_from_directory(session_path, filename)

@app.route('/api/projects/templates', methods=['GET'])
def get_templates():
    """Mock templates endpoint - returns empty templates for now"""
    page = request.args.get('page', '1')
    limit = request.args.get('limit', '4')
    
    # Return empty templates response for now
    # TODO: Implement actual templates functionality
    return jsonify({
        "data": [],
        "pagination": {
            "page": int(page),
            "limit": int(limit),
            "total": 0,
            "totalPages": 0
        }
    })



def chat_with_ai_about_design(messages, current_svg=None):
    """Enhanced conversational AI that can discuss and modify designs"""
    logger.info("Starting conversational AI interaction")
    logger.info(f"Processing {len(messages)} messages with {'SVG context' if current_svg else 'no context'}")

    # Create system prompt that includes SVG knowledge
    system_prompt = """You are an expert AI design assistant with deep knowledge of SVG creation and manipulation. You can:

1. Create new designs from scratch
2. Explain existing SVG designs in detail
3. Modify existing designs based on user feedback
4. Provide design suggestions and improvements
5. Discuss design principles, colors, typography, and layout

When discussing SVGs, you understand:
- SVG elements like <rect>, <circle>, <path>, <text>, <g>
- Attributes like fill, stroke, viewBox, transform
- Design principles like color theory, typography, layout
- How to make designs accessible and responsive

Guidelines:
- Be conversational and helpful
- Explain technical concepts in simple terms
- Ask clarifying questions when needed
- Provide specific suggestions for improvements
- When modifying designs, explain what changes you're making and why

Current context: You are helping a user with their design project."""

    if current_svg:
        system_prompt += f"\n\nCurrent SVG design context:\n```svg\n{current_svg}\n```\n\nYou can reference and modify this design based on user requests."

    # Prepare messages for the AI
    ai_messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history (limit to last 10 messages to manage context)
    conversation_messages = messages[-10:] if len(messages) > 10 else messages
    
    for msg in conversation_messages:
        if msg["role"] in ["user", "assistant"]:
            # Clean SVG code blocks from previous messages to avoid clutter
            content = msg["content"]
            if "```svg" in content and msg["role"] == "assistant":
                # Keep only the explanation part, not the SVG code
                parts = content.split("```svg")
                if len(parts) > 1:
                    explanation = parts[0].strip()
                    if explanation:
                        content = explanation
                    else:
                        content = "I provided a design based on your request."
            
            ai_messages.append({
                "role": msg["role"],
                "content": content
            })

    try:
        # Use OpenAI client directly instead of raw API calls
        client = openai.OpenAI(api_key=OPENAI_API_KEY_ENHANCER)
        response = client.chat.completions.create(
            model=CHAT_ASSISTANT_MODEL,
            messages=ai_messages,
            temperature=0.7,
            max_tokens=8000
        )
        
        # Extract the response content safely
        if response and response.choices and len(response.choices) > 0:
            ai_response = response.choices[0].message.content
            logger.info(f"AI response generated: {ai_response[:100]}...")
            return ai_response
        else:
            logger.error("Empty or invalid response from OpenAI")
            return "I apologize, but I'm having trouble generating a response. Could you please rephrase your request?"
            
    except Exception as e:
        logger.error(f"Error in chat_with_ai_about_design: {str(e)}")
        return "I apologize, but I encountered an error while processing your request. Please try again."

def modify_svg_with_ai(original_svg, modification_request):
    """Use AI to modify an existing SVG based on user request"""
    logger.info(f"Modifying SVG with request: {modification_request}")
    
    url = OPENAI_CHAT_ENDPOINT
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY_SVG}"
    }

    system_prompt = """You are an expert SVG modifier. Given an original SVG and a modification request, create a new SVG that incorporates the requested changes.

Rules:
1. Maintain the overall structure and quality of the original design
2. Make only the requested modifications
3. Ensure the SVG is valid and well-formed
4. Keep the viewBox and dimensions appropriate
5. Maintain good design principles
6. Return ONLY the modified SVG code, no explanations

The SVG should be production-ready and properly formatted."""

    payload = {
        "model": SVG_GENERATOR_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Original SVG:\n```svg\n{original_svg}\n```\n\nModification request: {modification_request}\n\nPlease provide the modified SVG:"
            }
        ],
        "temperature": 1,
        "max_tokens": 8000
    }

    logger.info("Calling AI for SVG modification")
    response = requests.post(url, headers=headers, json=payload)
    response_data = response.json()

    if response.status_code != 200:
        logger.error(f"SVG modification error: {response_data}")
        return None

    modified_content = response_data["choices"][0]["message"]["content"]
    
    # Extract SVG code
    svg_pattern = r'<svg.*?<\/svg>'
    svg_matches = re.search(svg_pattern, modified_content, re.DOTALL)
    
    if svg_matches:
        logger.info("Successfully modified SVG")
        return svg_matches.group(0)
    
    logger.warning("Could not extract modified SVG, returning original")
    return original_svg





def process_ocr_svg(image_data, session_id=None):
    """Generate a text-only SVG using enhanced OCR and AI-powered text analysis"""
    if not PARALLEL_FEATURES_AVAILABLE:
        raise NotImplementedError("Parallel features not available - missing dependencies")
    
    # Base64-encode the PNG image
    img_b64 = base64.b64encode(image_data).decode('utf-8')
    
    # Enhanced system prompt for accurate text detection
    system_prompt = """You are an expert OCR and SVG text specialist. Your task is to create PRECISE, ACCURATE SVG code that reproduces ALL text elements from the image with PERFECT positioning, sizing, and styling.

CRITICAL REQUIREMENTS:

1. **ACCURATE TEXT DETECTION**:
   - Detect ALL text in the image, including titles, subtitles, body text, captions, labels
   - Identify exact text content character by character
   - Don't miss any text elements, no matter how small or faint

2. **PRECISE FONT ANALYSIS**:
   - Analyze font family (serif, sans-serif, decorative, script)
   - Determine exact font weight (normal, bold, extra-bold)
   - Identify font style (normal, italic, oblique)
   - Estimate accurate font size in pixels

3. **EXACT POSITIONING**:
   - Measure precise x,y coordinates for each text element
   - Use percentages or absolute pixels for accurate placement
   - Maintain proper text alignment (left, center, right)
   - Preserve line spacing and letter spacing

4. **COLOR MATCHING**:
   - Extract exact colors using hex codes (#RRGGBB)
   - Match text colors precisely from the image
   - Account for text shadows or effects if present

5. **SVG STRUCTURE**:
   - Use viewBox="0 0 1080 1080" and dimensions 1080x1080
   - Include proper text-anchor attributes (start, middle, end)
   - Use <defs> for font loading and styling
   - Group related text elements logically

6. **QUALITY STANDARDS**:
   - Text must be crisp and readable
   - Maintain proper hierarchy (titles larger than subtitles)
   - Ensure text doesn't overlap unless intended
   - Optimize for web rendering

EXAMPLE STRUCTURE:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="1080" height="1080">
  <defs>
    <style>
      .main-title { font-family: 'Arial Black', sans-serif; font-size: 120px; fill: #2E3A99; font-weight: bold; }
      .subtitle { font-family: 'Arial', sans-serif; font-size: 48px; fill: #FFFFFF; font-weight: normal; }
    </style>
  </defs>
  <text x="540" y="300" class="main-title" text-anchor="middle">EXACT TEXT</text>
  <text x="540" y="400" class="subtitle" text-anchor="middle">Subtitle Text</text>
</svg>
```

Return ONLY the complete SVG code with ALL text elements accurately positioned and styled."""

    user_content = [
        {"type": "text", "text": "Analyze this image and extract ALL text elements with PRECISE positioning, font sizing, colors, and styling. Create accurate SVG code that reproduces the text exactly as shown in the image."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
    ]
    
    # Call Chat Completions API directly to support image_url message with enhanced parameters
    payload = {
        "model": "gpt-4.1-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 1,  # Lower temperature for more consistent text detection
        "max_tokens": 12000,  # More tokens for detailed SVG output# Avoid repetitive patterns
    }
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY_SVG}"
    }
    
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    
    if response.status_code != 200:
        logger.error(f"Error generating text SVG: {data}")
        raise Exception("Text SVG generation failed")
    
    content = data["choices"][0]["message"]["content"]
    
    # Extract the SVG
    match = re.search(r'<svg.*?</svg>', content, re.DOTALL)
    svg_code = match.group(0) if match else content.strip()
    
    # Save and return
    svg_filename, svg_relative_path, returned_session_id = save_svg(svg_code, prefix='text_svg', session_id=session_id)
    return svg_code, svg_relative_path

def process_background_extraction(image_data, session_id=None):
    """Intelligent background extraction using GPT-4o-mini analysis + Flux Kontext Pro"""
    logger.info("Starting intelligent background extraction with GPT-4o-mini analysis...")
    
    try:
        # Convert image data to base64 for Flux input
        input_image_base64 = base64.b64encode(image_data).decode('utf-8')
        input_image_data_url = f"data:image/png;base64,{input_image_base64}"
        
        # Step 1: Use GPT-4o-mini to analyze image and generate detailed background extraction prompt
        logger.info("🔍 Step 1: Analyzing image with GPT-4o-mini...")
        background_prompt = analyze_background_with_gpt4o_mini(input_image_base64)
        logger.info(f"📝 Generated intelligent prompt: {background_prompt[:200]}...")
        
        # Step 2: Use Flux Kontext Pro with the intelligent prompt
        logger.info("🎨 Step 2: Sending to Flux Kontext Pro for background extraction...")
        output = replicate.run(
            "black-forest-labs/flux-kontext-pro",
            input={
                "prompt": background_prompt,
                "input_image": input_image_data_url,
                "aspect_ratio": "match_input_image",
                "output_format": "jpg",
                "safety_tolerance": 2,
                "prompt_upsampling": False
            }
        )
        
        # Get the background-only image URL and download it
        background_url = output[0] if isinstance(output, list) else output
        response = requests.get(background_url)
        background_base64 = base64.b64encode(response.content).decode('utf-8')
        
        # Create session and save to unified storage
        if not session_id:
            session_id = f"bg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        background_filename, background_relative_path, _ = save_image(background_base64, prefix="background", session_id=session_id)
        background_full_path = os.path.join(IMAGES_DIR, background_relative_path)
        
        # Create public URL for the background
        background_public_url = get_public_image_url(background_relative_path)
        
        logger.info(f"✅ Intelligent background extraction completed: {background_filename}")
        logger.info(f"🌐 Background public URL: {background_public_url}")
        return background_base64, background_filename, background_full_path, background_public_url
        
    except Exception as e:
        logger.error(f"Error in background extraction: {str(e)}")
        # Fallback: return original image as background using unified storage
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        if not session_id:
            session_id = f"bgfb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        fallback_filename, fallback_relative_path, _ = save_image(image_base64, prefix="background_fallback", session_id=session_id)
        fallback_full_path = os.path.join(IMAGES_DIR, fallback_relative_path)
        
        # Create public URL for fallback
        fallback_public_url = get_public_image_url(fallback_relative_path)
        
        logger.warning("Using original image as background fallback")
        logger.info(f"Fallback background public URL: {fallback_public_url}")
        return image_base64, fallback_filename, fallback_full_path, fallback_public_url

def process_clean_svg(image_data):
    """Process text AND background removal and convert to clean SVG (elements only)"""
    if not VTRACER_AVAILABLE:
        raise NotImplementedError("VTracer not available - missing core dependency")
    
    # Save the original image bytes to a temporary PNG file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_input_path = f"temp_input_{timestamp}_{uuid.uuid4()}.png"
    with open(temp_input_path, "wb") as f:
        f.write(image_data)

    try:
        # If remove_text_simple is available, use it for text removal
        if REMOVE_TEXT_AVAILABLE:
            final_edited_path = remove_text_simple.remove_text(temp_input_path)
            logger.info("Text removed from image, proceeding with V-Tracer for element isolation...")
        else:
            # Skip text removal if not available
            final_edited_path = temp_input_path
            logger.info("Text removal not available, proceeding with V-Tracer using original image...")

        # Preprocess for vtracer: use gradient-friendly preprocessing
        pre_vtracer_path = preprocess_for_gradients(final_edited_path)

        output_svg_path = os.path.join(IMAGES_DIR, f"elements_{timestamp}_{uuid.uuid4().hex[:8]}.svg")
        vtracer.convert_image_to_svg_py(
            pre_vtracer_path,
            output_svg_path
        )

        # Read the generated SVG
        with open(output_svg_path, 'r', encoding='utf-8') as f:
            svg_code = f.read()

        return svg_code, os.path.basename(output_svg_path), final_edited_path
    finally:
        # Clean up temporary files
        for temp_file in [temp_input_path]:
            if os.path.exists(temp_file):
                os.remove(temp_file)

def preprocess_for_vtracer(input_path):
    """Improved preprocessing for VTracer to enhance element separation and detail"""
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    import numpy as np
    import cv2

    img = Image.open(input_path).convert('RGB')
    # Less aggressive posterization
    img = ImageOps.posterize(img, 4)  # 4 bits = 16 colors per channel
    # Increase contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    # Optional: Sharpen
    img = img.filter(ImageFilter.SHARPEN)
    # Convert to numpy for OpenCV denoising
    img_np = np.array(img)
    img_np = cv2.fastNlMeansDenoisingColored(img_np, None, 10, 10, 7, 21)
    # Optional: Slight blur to reduce noise
    img_np = cv2.GaussianBlur(img_np, (3, 3), 0.5)
    pre_path = input_path.replace('.png', '_pre_vtracer.png')
    Image.fromarray(img_np).save(pre_path)
    return pre_path
    
def preprocess_for_gradients(input_path):
    """Minimal preprocessing specifically for gradient-rich images"""
    # Load image
    img = Image.open(input_path).convert('RGB')
    
    # Very light posterization to maintain gradient smoothness
    img = ImageOps.posterize(img, 6)  # ✅ 6 bits = 64 colors per channel
    
    # Convert to numpy array for OpenCV
    img_np = np.array(img)
    
    # Very light gaussian blur to smooth small artifacts only
    img_np = cv2.GaussianBlur(img_np, (3, 3), 0.5)
    
    # Save preprocessed image
    pre_path = input_path.replace('.png', '_gradient_pre.png')
    Image.fromarray(img_np).save(pre_path)
    return pre_path



def ai_combine_svgs(text_svg_code, elements_svg_code, background_image_url=None):
    """OPTIMIZED AI-powered combination of text, elements SVGs and background image"""
    logger.info("Using OPTIMIZED AI to combine 3-layer SVG...")
    
    # Simplified system prompt for faster processing
    system_prompt = """You are an SVG combiner. Create a single SVG with 3 layers:
1. Background: <image href="URL" x="0" y="0" width="1080" height="1080"/>
2. Elements: Graphics from elements SVG
3. Text: Text from text SVG

Structure:
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="1080" height="1080">
  <g id="background-layer">[background]</g>
  <g id="elements-layer">[elements]</g>
  <g id="text-layer">[text]</g>
</svg>

Return ONLY the SVG code."""

    # Truncate SVG codes for faster processing
    max_svg_length = 15000
    if len(text_svg_code) > max_svg_length:
        text_svg_code = text_svg_code[:max_svg_length] + "</svg>"
    if len(elements_svg_code) > max_svg_length:
        elements_svg_code = elements_svg_code[:max_svg_length] + "</svg>"

    user_prompt = f"""Combine these into a 3-layer SVG:

TEXT SVG:
{text_svg_code}

ELEMENTS SVG:
{elements_svg_code}

Background URL: {background_image_url}

Return the combined SVG."""

    # Use optimized call with faster model
    ai_response = optimized_openai_call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model="gpt-4.1-mini",  # Faster model
        max_tokens=32000,      # Reduced tokens
        temperature=1      # More deterministic
    )
    
    if ai_response:
        logger.info("AI successfully combined 3-layer SVG - optimized version")
        return ai_response
    else:
        logger.info("AI call failed, using fallback")
        return simple_combine_svgs_fallback(text_svg_code, elements_svg_code, background_image_url)

def simple_combine_svgs_fallback(text_svg_code, elements_svg_code, background_image_url=None):
    """Fallback simple combination method with improved error handling for 3 layers"""
    try:
        logger.info("Using fallback 3-layer SVG combination method")
        
        # Validate inputs
        if not text_svg_code or not elements_svg_code:
            logger.warning("Missing SVG input data for fallback")
            return elements_svg_code if elements_svg_code else text_svg_code
        
        # Extract content from both SVGs
        text_match = re.search(r'<svg[^>]*>(.*?)</svg>', text_svg_code, re.DOTALL | re.IGNORECASE)
        elements_match = re.search(r'<svg[^>]*>(.*?)</svg>', elements_svg_code, re.DOTALL | re.IGNORECASE)
        
        if not text_match:
            logger.warning("Could not extract text SVG content, using entire text SVG")
            text_content = text_svg_code
        else:
            text_content = text_match.group(1).strip()
            
        if not elements_match:
            logger.warning("Could not extract elements SVG content, using entire elements SVG")
            elements_content = elements_svg_code
        else:
            elements_content = elements_match.group(1).strip()
        
        # Prepare background layer using the provided URL
        background_layer = ""
        if background_image_url:
            background_layer = f'''<image href="{background_image_url}" x="0" y="0" width="1080" height="1080" preserveAspectRatio="xMidYMid slice"/>'''
        
        # Create combined SVG with 3-layer structure
        combined_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="1080" height="1080">
  <defs>
    <!-- Include any definitions from original SVGs -->
  </defs>
  <g id="background-layer">
    {background_layer}
  </g>
  <g id="elements-layer" opacity="0.9">
    {elements_content}
  </g>
  <g id="text-layer">
    {text_content}
  </g>
</svg>'''
        
        logger.info("Fallback 3-layer SVG combination completed successfully")
        return combined_svg
        
    except Exception as e:
        logger.error(f"Error in fallback 3-layer SVG combination: {str(e)}")
        logger.error(f"Text SVG preview: {text_svg_code[:100] if text_svg_code else 'None'}...")
        logger.error(f"Elements SVG preview: {elements_svg_code[:100] if elements_svg_code else 'None'}...")
        logger.error(f"Background URL: {background_image_url}")
        # Return the elements SVG as the safest fallback
        return elements_svg_code if elements_svg_code else text_svg_code

@app.route('/api/generate-parallel-svg', methods=['POST'])
def generate_parallel_svg():
    """Direct Parallel SVG Pipeline: Takes image input and runs triple parallel processing stages"""
    try:
        if not PARALLEL_FEATURES_AVAILABLE:
            return jsonify({
                "error": "Parallel SVG features not available",
                "message": "Missing required dependencies (vtracer, remove_text_simple, etc.)"
            }), 501

        data = request.json or {}
        image_base64 = data.get('image_base64', '')
        user_input = data.get('prompt', '')  # Optional for context/naming

        if not image_base64:
            return jsonify({'error': 'No image_base64 provided'}), 400

        logger.info('=== DIRECT PARALLEL SVG PIPELINE START ===')

        # Create unified session for parallel pipeline
        parallel_session_id = f"parallel_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        logger.info(f'Created parallel session: {parallel_session_id}')
        
        # Convert base64 to image data for processing
        try:
            image_data = base64.b64decode(image_base64)
            logger.info(f'Image data decoded successfully, size: {len(image_data)} bytes')
        except Exception as e:
            return jsonify({'error': f'Invalid image_base64 format: {str(e)}'}), 400
        
        # Save the input image to unified storage
        logger.info(f'Saving input image to unified storage session: {parallel_session_id}')
        input_image_filename, input_image_relative_path, _ = save_image(image_base64, prefix="input_image", session_id=parallel_session_id)

        # Stage 1: Triple Parallel Processing
        logger.info('Stage 1: Triple Parallel Processing - Text SVG, Background Extraction, and Elements SVG')
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all three tasks
            ocr_future = executor.submit(process_ocr_svg, image_data)
            background_future = executor.submit(process_background_extraction, image_data)
            elements_future = executor.submit(process_clean_svg, image_data)
            
            # Get results
            text_svg_code, text_svg_path = ocr_future.result()
            background_base64, background_filename, background_path, background_public_url = background_future.result()
            elements_svg_code, elements_svg_path, edited_png_path = elements_future.result()

        # Session already created above

        # Base URL for unified storage
        base_url = '/static/images/sessions'

        # Save all files directly to unified session folder using session_id
        try:
            # Initial image already saved above as 'initial_generated'
            
            # Save background image to unified storage
            _, background_relative_path, _ = save_image(background_base64, prefix="background", session_id=parallel_session_id)
            
            # Save text SVG to unified storage
            _, text_svg_relative_path, _ = save_svg(text_svg_code, prefix="text_svg", session_id=parallel_session_id)
            
            # Save elements SVG to unified storage
            _, elements_svg_relative_path, _ = save_svg(elements_svg_code, prefix="elements_svg", session_id=parallel_session_id)
            
            # Save elements PNG to unified storage
            with open(edited_png_path, 'rb') as f:
                edited_png_data = f.read()
            edited_png_base64 = base64.b64encode(edited_png_data).decode('utf-8')
            _, edited_png_relative_path, _ = save_image(edited_png_base64, prefix="elements_png", format="PNG", session_id=parallel_session_id)

        except Exception as e:
            logger.warning(f"Error saving files to unified storage: {e}")
            # Fallback to using original paths
            input_image_relative_path = input_image_filename
            background_relative_path = background_filename
            text_svg_relative_path = text_svg_path
            elements_svg_relative_path = elements_svg_path
            edited_png_relative_path = os.path.basename(edited_png_path)

        # Construct PUBLIC URLs for serving using unified storage paths  
        input_image_public_url = get_public_image_url(f"sessions/{parallel_session_id}/{input_image_filename}")
        text_svg_public_url = get_public_image_url(f"sessions/{parallel_session_id}/{os.path.basename(text_svg_relative_path)}")
        # Use the background_public_url we already have from the background extraction
        elements_svg_public_url = get_public_image_url(f"sessions/{parallel_session_id}/{os.path.basename(elements_svg_relative_path)}")
        edited_png_public_url = get_public_image_url(f"sessions/{parallel_session_id}/{os.path.basename(edited_png_relative_path)}")

        # Log all public URLs for debugging
        logger.info(f"Generated public URLs:")
        logger.info(f"  Input image: {input_image_public_url}")
        logger.info(f"  Background: {background_public_url}")
        logger.info(f"  Text SVG: {text_svg_public_url}")
        logger.info(f"  Elements SVG: {elements_svg_public_url}")
        logger.info(f"  Elements PNG: {edited_png_public_url}")

        # Also create relative URLs for backward compatibility in response
        input_image_url = f"{base_url}/{parallel_session_id}/{input_image_filename}"
        text_svg_url = f"{base_url}/{parallel_session_id}/{os.path.basename(text_svg_relative_path)}"
        background_url = f"{base_url}/{parallel_session_id}/{os.path.basename(background_relative_path)}"
        elements_svg_url = f"{base_url}/{parallel_session_id}/{os.path.basename(elements_svg_relative_path)}"
        edited_png_url = f"{base_url}/{parallel_session_id}/{os.path.basename(edited_png_relative_path)}"

        # Stage 2: AI-Powered 3-Layer SVG Combination using PUBLIC URLs for proper embedding
        logger.info('Stage 2: AI-Powered 3-Layer SVG Combination using gpt-4o-mini with PUBLIC background URL')
        logger.info(f'Using public background URL for SVG combination: {background_public_url}')
        combined_svg_code = ai_combine_svgs(text_svg_code, elements_svg_code, background_public_url)
        
        # Validate the combined SVG
        if not combined_svg_code or not combined_svg_code.strip():
            logger.error("Combined SVG is empty, using fallback with public URL")
            combined_svg_code = simple_combine_svgs_fallback(text_svg_code, elements_svg_code, background_public_url)
        
        # Ensure the SVG is well-formed
        if not combined_svg_code.strip().startswith('<svg'):
            logger.warning("Combined SVG doesn't start with <svg, using fallback with public URL")
            combined_svg_code = simple_combine_svgs_fallback(text_svg_code, elements_svg_code, background_public_url)
        
        # Stage 3: Post-process SVG with OpenAI to remove first path in elements-layer
        logger.info('Stage 3: Post-processing SVG to remove first path in elements-layer using gpt-4o-mini')
        combined_svg_code = post_process_svg_remove_first_path(combined_svg_code)
        
        # Save combined SVG to unified storage
        combined_svg_filename, combined_svg_relative_path, _ = save_svg(combined_svg_code, prefix="combined_svg", session_id=parallel_session_id)
        
        logger.info(f"Combined SVG saved successfully: {combined_svg_filename}")

        # Final combined SVG URL
        combined_svg_url = f"{base_url}/{parallel_session_id}/{combined_svg_filename}"

        # Add AI-based SVG correction step
        force_svg_fix = data.get('force_svg_fix', False)
        svg_fixed = False
        max_svg_fix_attempts = 2
        svg_fix_attempts = 0
        elements_svg_code_fixed = elements_svg_code
        while svg_fix_attempts < max_svg_fix_attempts:
            # Heuristic: If force_svg_fix is set, or SVG is too small/empty, or user wants retry
            if force_svg_fix or len(elements_svg_code_fixed) < 500 or '<path' not in elements_svg_code_fixed:
                logger.info(f"Attempting AI-based SVG correction (attempt {svg_fix_attempts+1})...")
                elements_svg_code_fixed = ai_fix_svg_with_png(elements_svg_code_fixed, edited_png_public_url, user_input)
                svg_fix_attempts += 1
                # If SVG is now much larger and contains paths, break
                if len(elements_svg_code_fixed) > 500 and '<path' in elements_svg_code_fixed:
                    svg_fixed = True
                    break
            else:
                break
        # If still not usable, try to regenerate from scratch (fallback)
        if not svg_fixed and (force_svg_fix or len(elements_svg_code_fixed) < 500 or '<path' not in elements_svg_code_fixed):
            logger.warning("SVG still not usable after AI fix, regenerating elements SVG from scratch...")
            # Regenerate using process_clean_svg again
            elements_svg_code_fixed, elements_svg_path, edited_png_path = process_clean_svg(image_data)
            # Save new SVG and PNG
            _, elements_svg_relative_path, _ = save_svg(elements_svg_code_fixed, prefix="elements_svg_regen", session_id=parallel_session_id)
            with open(edited_png_path, 'rb') as f:
                edited_png_data = f.read()
            edited_png_base64 = base64.b64encode(edited_png_data).decode('utf-8')
            _, edited_png_relative_path, _ = save_image(edited_png_base64, prefix="elements_png_regen", format="PNG", session_id=parallel_session_id)
            elements_svg_public_url = get_public_image_url(f"sessions/{parallel_session_id}/{os.path.basename(elements_svg_relative_path)}")
            edited_png_public_url = get_public_image_url(f"sessions/{parallel_session_id}/{os.path.basename(edited_png_relative_path)}")
        else:
            # Save the fixed SVG if it was changed
            if svg_fixed:
                _, elements_svg_relative_path, _ = save_svg(elements_svg_code_fixed, prefix="elements_svg_fixed", session_id=parallel_session_id)
                elements_svg_public_url = get_public_image_url(f"sessions/{parallel_session_id}/{os.path.basename(elements_svg_relative_path)}")
        # Use elements_svg_code_fixed for all downstream steps
        elements_svg_code = elements_svg_code_fixed

        return jsonify({
            'original_prompt': user_input,
            'input_image': {
                'url': input_image_url,
                'public_url': input_image_public_url,
                'path': input_image_relative_path,
                'filename': input_image_filename
            },
            'background': {
                'base64': background_base64,
                'path': f"sessions/{parallel_session_id}/{os.path.basename(background_relative_path)}",
                'url': background_url,
                'public_url': background_public_url
            },
            'elements_png': {
                'path': f"sessions/{parallel_session_id}/{os.path.basename(edited_png_relative_path)}",
                'url': edited_png_url,
                'public_url': edited_png_public_url
            },
            'text_svg': {
                'code': text_svg_code,
                'path': f"sessions/{parallel_session_id}/{os.path.basename(text_svg_relative_path)}",
                'url': text_svg_url,
                'public_url': text_svg_public_url
            },
            'elements_svg': {
                'code': elements_svg_code,
                'path': f"sessions/{parallel_session_id}/{os.path.basename(elements_svg_relative_path)}",
                'url': elements_svg_url,
                'public_url': elements_svg_public_url
            },
            'combined_svg': {
                'code': combined_svg_code,
                'path': combined_svg_relative_path,
                'url': combined_svg_url,
                'public_url': get_public_image_url(combined_svg_relative_path)
            },
            'session_id': parallel_session_id,
            'stage': 3,
            'note': 'Direct parallel SVG processing from input image'
        })

    except Exception as e:
        logger.error(f"Error in generate_parallel_svg: {str(e)}")
        return jsonify({"error": str(e)}), 500











# Add caching for OpenAI responses
@lru_cache(maxsize=100)
def get_cached_openai_response(prompt_hash, model, system_prompt_hash):
    """Cache OpenAI responses to avoid repeated API calls for similar requests"""
    return None

def generate_prompt_hash(prompt):
    """Generate a hash for prompt caching"""
    return hashlib.md5(prompt.encode()).hexdigest()

# Create a global session with connection pooling for OpenAI API calls
def create_optimized_session():
    """Create a requests session with connection pooling and retry strategy"""
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=2,  # Reduced retries for faster failure
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"],
        backoff_factor=0.3  # Reduced backoff for speed
    )
    
    # Configure adapter with connection pooling
    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=retry_strategy
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# Global session for reuse
openai_session = create_optimized_session()

# Performance monitoring for OpenAI API calls
api_performance_stats = {
    'total_calls': 0,
    'total_time': 0,
    'avg_response_time': 0,
    'fastest_call': float('inf'),
    'slowest_call': 0,
    'success_rate': 0,
    'failures': 0
}

def log_api_performance(response_time, success=True):
    """Log API performance metrics"""
    global api_performance_stats
    
    api_performance_stats['total_calls'] += 1
    if success:
        api_performance_stats['total_time'] += response_time
        api_performance_stats['fastest_call'] = min(api_performance_stats['fastest_call'], response_time)
        api_performance_stats['slowest_call'] = max(api_performance_stats['slowest_call'], response_time)
        api_performance_stats['avg_response_time'] = api_performance_stats['total_time'] / (api_performance_stats['total_calls'] - api_performance_stats['failures'])
    else:
        api_performance_stats['failures'] += 1
    
    api_performance_stats['success_rate'] = ((api_performance_stats['total_calls'] - api_performance_stats['failures']) / api_performance_stats['total_calls']) * 100
    
    if api_performance_stats['total_calls'] % 5 == 0:  # Log every 5 calls
        logger.info(f"OpenAI API Performance Stats: Avg: {api_performance_stats['avg_response_time']:.2f}s, "
                   f"Range: {api_performance_stats['fastest_call']:.2f}s-{api_performance_stats['slowest_call']:.2f}s, "
                   f"Success Rate: {api_performance_stats['success_rate']:.1f}%")

# Optimized OpenAI API call with streaming and reduced payload
def optimized_openai_call(system_prompt, user_prompt, model="gpt-4o-mini", max_tokens=8000, temperature=0.3):
    """Optimized OpenAI API call with connection pooling, caching, and reduced payload"""
    import time
    
    # Generate cache keys
    prompt_hash = generate_prompt_hash(user_prompt)
    system_hash = generate_prompt_hash(system_prompt)
    
    logger.info(f"Making OPTIMIZED OpenAI call: {model}, tokens: {max_tokens}, prompt_size: {len(user_prompt)}")
    
    url = OPENAI_CHAT_ENDPOINT
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY_SVG}",
        "Connection": "keep-alive"  # Enable connection reuse
    }

    # Reduce prompt sizes to speed up processing
    original_prompt_size = len(user_prompt)
    if len(user_prompt) > 30000:
        logger.info(f"Truncating user prompt from {len(user_prompt)} to 30000 chars for faster processing")
        user_prompt = user_prompt[:30000] + "...\n\nPLEASE PROCESS THE ABOVE SVG CONTENT."
    
    if len(system_prompt) > 8000:
        logger.info(f"Truncating system prompt from {len(system_prompt)} to 8000 chars for faster processing")
        system_prompt = system_prompt[:8000] + "..."

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user", 
                "content": user_prompt
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }

    start_time = time.time()
    try:
        # Use the global session with connection pooling
        response = openai_session.post(url, headers=headers, json=payload, timeout=80)
        api_response_time = time.time() - start_time
        
        # Log performance
        log_api_performance(api_response_time, success=True)
        
        logger.info(f"[SUCCESS] OPTIMIZED OpenAI API response in {api_response_time:.2f}s (was {original_prompt_size} chars)")

        if response.status_code != 200:
            logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
            log_api_performance(api_response_time, success=False)
            return None

        response_data = response.json()
        ai_response = response_data["choices"][0]["message"]["content"]
        
        return ai_response.strip()
            
    except Exception as e:
        api_response_time = time.time() - start_time
        log_api_performance(api_response_time, success=False)
        logger.error(f"[ERROR] Error in optimized OpenAI call after {api_response_time:.2f}s: {str(e)}")
        return None

# Add endpoint to check API performance stats




def simple_combine_svgs_fallback(text_svg_code, elements_svg_code, background_image_url=None):
    """Fallback simple combination method with improved error handling for 3 layers"""
    try:
        logger.info("Using fallback 3-layer SVG combination method")
        
        # Validate inputs
        if not text_svg_code or not elements_svg_code:
            logger.warning("Missing SVG input data for fallback")
            return elements_svg_code if elements_svg_code else text_svg_code
        
        # Extract content from both SVGs
        text_match = re.search(r'<svg[^>]*>(.*?)</svg>', text_svg_code, re.DOTALL | re.IGNORECASE)
        elements_match = re.search(r'<svg[^>]*>(.*?)</svg>', elements_svg_code, re.DOTALL | re.IGNORECASE)
        
        if not text_match:
            logger.warning("Could not extract text SVG content, using entire text SVG")
            text_content = text_svg_code
        else:
            text_content = text_match.group(1).strip()
            
        if not elements_match:
            logger.warning("Could not extract elements SVG content, using entire elements SVG")
            elements_content = elements_svg_code
        else:
            elements_content = elements_match.group(1).strip()
        
        # Prepare background layer using the provided URL
        background_layer = ""
        if background_image_url:
            background_layer = f'''<image href="{background_image_url}" x="0" y="0" width="1080" height="1080" preserveAspectRatio="xMidYMid slice"/>'''
        
        # Create combined SVG with 3-layer structure
        combined_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="1080" height="1080">
  <defs>
    <!-- Include any definitions from original SVGs -->
  </defs>
  <g id="background-layer">
    {background_layer}
  </g>
  <g id="elements-layer" opacity="0.9">
    {elements_content}
  </g>
  <g id="text-layer">
    {text_content}
  </g>
</svg>'''
        
        logger.info("Fallback 3-layer SVG combination completed successfully")
        return combined_svg
        
    except Exception as e:
        logger.error(f"Error in fallback 3-layer SVG combination: {str(e)}")
        logger.error(f"Text SVG preview: {text_svg_code[:100] if text_svg_code else 'None'}...")
        logger.error(f"Elements SVG preview: {elements_svg_code[:100] if elements_svg_code else 'None'}...")
        logger.error(f"Background URL: {background_image_url}")
        # Return the elements SVG as the safest fallback
        return elements_svg_code if elements_svg_code else text_svg_code



# Add OpenRouter configuration near the top with other API configurations
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    logger.warning("🔧 OPENROUTER_API_KEY not set. Add it to your environment variables for Google Gemini-2.5-flash support!")
    logger.warning("   Example: export OPENROUTER_API_KEY='sk-or-v1-your-key-here'")
    logger.warning("   Get your key at: https://openrouter.ai/")
    logger.warning("   Will fall back to OpenAI API for SVG operations")
else:
    logger.info("[SUCCESS] OpenRouter API key found - Google Gemini-2.5-flash enabled for ultra-fast SVG processing!")

# OpenRouter client for SVG operations
openrouter_client = None
if OPENROUTER_API_KEY:
    from openai import OpenAI
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

def optimized_openrouter_call(system_prompt, user_prompt, model="google/gemini-2.5-flash", max_tokens=8000, temperature=0.3):
    """Optimized OpenRouter API call using Google Gemini-2.5-flash"""
    import time
    
    if not openrouter_client:
        logger.error("OpenRouter client not initialized, falling back to OpenAI")
        return optimized_openai_call(system_prompt, user_prompt, "gpt-4o-mini", max_tokens, temperature)
    
    logger.info(f"Making OPTIMIZED OpenRouter call: {model}, tokens: {max_tokens}, prompt_size: {len(user_prompt)}")
    
    # Reduce prompt sizes to speed up processing
    original_prompt_size = len(user_prompt)
    if len(user_prompt) > 30000:
        logger.info(f"Truncating user prompt from {len(user_prompt)} to 30000 chars for faster processing")
        user_prompt = user_prompt[:30000] + "...\n\nPLEASE PROCESS THE ABOVE SVG CONTENT."
    
    if len(system_prompt) > 8000:
        logger.info(f"Truncating system prompt from {len(system_prompt)} to 8000 chars for faster processing")
        system_prompt = system_prompt[:8000] + "..."

    start_time = time.time()
    try:
        completion = openrouter_client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://infoui.app",  # Your site URL
                "X-Title": "InfoUI SVG Generator",     # Your site name
            },
            extra_body={},
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": user_prompt
                }
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        api_response_time = time.time() - start_time
        
        # Log performance
        log_api_performance(api_response_time, success=True)
        
        logger.info(f"[SUCCESS] OPTIMIZED OpenRouter API response in {api_response_time:.2f}s (was {original_prompt_size} chars)")

        ai_response = completion.choices[0].message.content
        return ai_response.strip()
            
    except Exception as e:
        api_response_time = time.time() - start_time
        log_api_performance(api_response_time, success=False)
        logger.error(f"[ERROR] Error in optimized OpenRouter call after {api_response_time:.2f}s: {str(e)}")
        return None

def normal_combine_svgs(text_svg_code, elements_svg_code, background_image_url=None):
    """Normal function to combine SVGs in the specified structure without AI dependency"""
    try:
        logger.info("Creating structured 3-layer SVG combination...")
        
        # Validate inputs
        if not text_svg_code and not elements_svg_code:
            logger.warning("No SVG content provided")
            return ""
        
        # Extract content from text SVG
        def extract_svg_content(svg_code):
            """Extract the inner content of an SVG (between svg tags)"""
            if not svg_code:
                return ""
            try:
                # Find content between <svg> and </svg> tags
                start_match = re.search(r'<svg[^>]*>', svg_code, re.IGNORECASE | re.DOTALL)
                end_match = re.search(r'</svg>', svg_code, re.IGNORECASE)
                
                if start_match and end_match:
                    start_pos = start_match.end()
                    end_pos = end_match.start()
                    content = svg_code[start_pos:end_pos].strip()
                    return content
                else:
                    # If no SVG tags found, return as-is (might be inner content already)
                    return svg_code.strip()
            except Exception as e:
                logger.warning(f"Error extracting SVG content: {e}")
                return svg_code.strip()
        
        # Extract text and elements content
        text_content = extract_svg_content(text_svg_code) if text_svg_code else ""
        elements_content = extract_svg_content(elements_svg_code) if elements_svg_code else ""
        
        # Prepare background layer
        background_layer = ""
        if background_image_url:
            background_layer = f'<image href="{background_image_url}" x="0" y="0" width="1080" height="1080" preserveAspectRatio="xMidYMid slice"/>'
        
        # Create the structured combined SVG following the exact format specified
        combined_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="1080" height="1080">
  <defs>
    <!-- Include any definitions from original SVGs -->
  </defs>
  <g id="background-layer">
    {background_layer}
  </g>
  <g id="elements-layer" opacity="0.9">
    {elements_content}
  </g>
  <g id="text-layer">
    {text_content}
  </g>
</svg>'''
        
        logger.info("✅ Successfully created structured 3-layer SVG combination")
        return combined_svg
        
    except Exception as e:
        logger.error(f"Error in normal SVG combination: {str(e)}")
        # Fallback to simple combination
        return simple_combine_svgs_fallback(text_svg_code, elements_svg_code, background_image_url)

def ai_combine_svgs(text_svg_code, elements_svg_code, background_image_url=None):
    """Normal function to combine SVGs without AI dependency"""
    logger.info("Using normal function to combine 3-layer SVG...")
    return normal_combine_svgs(text_svg_code, elements_svg_code, background_image_url)

def simple_combine_svgs_fallback(text_svg_code, elements_svg_code, background_image_url=None):
    """Fallback simple combination method with improved error handling for 3 layers"""
    try:
        logger.info("Using fallback 3-layer SVG combination method")
        
        # Validate inputs
        if not text_svg_code or not elements_svg_code:
            logger.warning("Missing SVG input data for fallback")
            return elements_svg_code if elements_svg_code else text_svg_code
        
        # Extract content from both SVGs
        text_match = re.search(r'<svg[^>]*>(.*?)</svg>', text_svg_code, re.DOTALL | re.IGNORECASE)
        elements_match = re.search(r'<svg[^>]*>(.*?)</svg>', elements_svg_code, re.DOTALL | re.IGNORECASE)
        
        if not text_match:
            logger.warning("Could not extract text SVG content, using entire text SVG")
            text_content = text_svg_code
        else:
            text_content = text_match.group(1).strip()
            
        if not elements_match:
            logger.warning("Could not extract elements SVG content, using entire elements SVG")
            elements_content = elements_svg_code
        else:
            elements_content = elements_match.group(1).strip()
        
        # Prepare background layer using the provided URL
        background_layer = ""
        if background_image_url:
            background_layer = f'''<image href="{background_image_url}" x="0" y="0" width="1080" height="1080" preserveAspectRatio="xMidYMid slice"/>'''
        
        # Create combined SVG with 3-layer structure
        combined_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="1080" height="1080">
  <defs>
    <!-- Include any definitions from original SVGs -->
  </defs>
  <g id="background-layer">
    {background_layer}
  </g>
  <g id="elements-layer" opacity="0.9">
    {elements_content}
  </g>
  <g id="text-layer">
    {text_content}
  </g>
</svg>'''
        
        logger.info("Fallback 3-layer SVG combination completed successfully")
        return combined_svg
        
    except Exception as e:
        logger.error(f"Error in fallback 3-layer SVG combination: {str(e)}")
        logger.error(f"Text SVG preview: {text_svg_code[:100] if text_svg_code else 'None'}...")
        logger.error(f"Elements SVG preview: {elements_svg_code[:100] if elements_svg_code else 'None'}...")
        logger.error(f"Background URL: {background_image_url}")
        # Return the elements SVG as the safest fallback
        return elements_svg_code if elements_svg_code else text_svg_code

def post_process_svg_remove_first_path(svg_code):
    """Normal post-processing to remove first path in elements-layer"""
    logger.info("Post-processing SVG to remove first path in elements-layer...")
    
    # Use regex-based approach
    try:
        import re
        
        # Find elements-layer group and remove first path
        pattern = r'(<g id="elements-layer"[^>]*>)(.*?)</g>'
        match = re.search(pattern, svg_code, re.DOTALL)
        
        if match:
            elements_content = match.group(2)
            # Remove first path tag
            path_pattern = r'<path[^>]*(?:/>|>.*?</path>)'
            elements_content_modified = re.sub(path_pattern, '', elements_content, count=1)
            
            # Replace in original SVG
            modified_svg = svg_code.replace(match.group(0), match.group(1) + elements_content_modified + '</g>')
            logger.info("✅ Successfully removed first path using regex")
            return modified_svg
        else:
            logger.info("No elements-layer found, returning original SVG")
            return svg_code
        
    except Exception as e:
        logger.warning(f"Regex approach failed: {str(e)}, returning original SVG")
        return svg_code

def convert_image_to_svg_stages_7_8_9(image_data: bytes):
    """
    Convert image data to SVG using InfoUI Stages 7-9 parallel processing
    All files are saved in the same session subfolder
    """
    try:
        logger.info("=== InfoUI STAGES 7-8-9 CONVERSION START ===")
        
        if not VTRACER_AVAILABLE:
            return {
                'success': False,
                'combined_svg': '',
                'text_svg': '',
                'elements_svg': '',
                'background_base64': '',
                'error': 'VTracer not available - InfoUI stages 7-8-9 require VTracer'
            }
        
        # Create shared session ID for all files in this conversion
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shared_session_id = f"infoui_stages_7_8_9_{timestamp}_{uuid.uuid4().hex[:8]}"
        logger.info(f"🗂️  Created shared session: {shared_session_id}")
        
        # Save the initial input image to the shared session
        initial_image_base64 = base64.b64encode(image_data).decode('utf-8')
        save_image(initial_image_base64, prefix="initial_input", session_id=shared_session_id)
        logger.info(f"💾 Initial input image saved to session: {shared_session_id}")
        
        # Stage 7: Triple Parallel Processing
        logger.info('Stage 7: Triple Parallel Processing - Text SVG, Background Extraction, and Elements SVG')
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all three tasks with shared session ID
            ocr_future = executor.submit(process_ocr_svg_with_session, image_data, shared_session_id)
            background_future = executor.submit(process_background_extraction_with_session, image_data, shared_session_id)
            elements_future = executor.submit(process_clean_svg_with_session, image_data, shared_session_id)
            
            # Get results
            text_svg_code, text_svg_path = ocr_future.result()
            background_base64, background_filename, background_path, background_public_url = background_future.result()
            elements_svg_code, elements_svg_path, edited_png_path = elements_future.result()
        
        # Stage 8: Normal 3-Layer SVG Combination  
        logger.info('Stage 8: Normal 3-Layer SVG Combination using structured approach')
        combined_svg_code = ai_combine_svgs_with_session(text_svg_code, elements_svg_code, background_public_url, shared_session_id)
        
        # Validate the combined SVG
        if not combined_svg_code or not combined_svg_code.strip():
            logger.error("Combined SVG is empty, using fallback")
            combined_svg_code = simple_combine_svgs_fallback(text_svg_code, elements_svg_code, background_public_url)
        
        # Stage 9: Post-process SVG
        logger.info('Stage 9: Post-processing SVG to remove first path in elements-layer')
        combined_svg_code = post_process_svg_remove_first_path_with_session(combined_svg_code, shared_session_id)
        
        logger.info("=== InfoUI STAGES 7-8-9 CONVERSION COMPLETE ===")
        logger.info(f"🗂️  All files saved in session: {shared_session_id}")
        
        # List all files that were saved to the session
        session_folder = os.path.join(IMAGES_DIR, shared_session_id)
        if os.path.exists(session_folder):
            files = os.listdir(session_folder)
            logger.info(f"📁 Session folder contains {len(files)} files:")
            for file in files:
                logger.info(f"   📄 {file}")
        
        return {
            'success': True,
            'combined_svg': combined_svg_code,
            'text_svg': text_svg_code,
            'elements_svg': elements_svg_code,
            'background_base64': background_base64,
            'session_id': shared_session_id,
            'error': ''
        }
        
    except Exception as e:
        logger.error(f"Error in convert_image_to_svg_stages_7_8_9: {str(e)}")
        return {
            'success': False,
            'combined_svg': '',
            'text_svg': '',
            'elements_svg': '',
            'background_base64': '',
            'error': str(e)
        }

def process_ocr_svg_with_session(image_data, session_id):
    """Generate text SVG and save to shared session"""
    text_svg_code, text_svg_path = process_ocr_svg(image_data, session_id)
    # Text SVG is already saved to the shared session by the function
    return text_svg_code, text_svg_path

def process_background_extraction_with_session(image_data, session_id):
    """Extract background and save to shared session"""
    background_base64, background_filename, background_path, background_public_url = process_background_extraction(image_data, session_id)
    # Background is already saved to the shared session by the function
    return background_base64, background_filename, background_path, background_public_url

def process_clean_svg_with_session(image_data, session_id):
    """Process clean SVG and save to shared session"""
    elements_svg_code, elements_svg_path, edited_png_path = process_clean_svg(image_data)
    # Save to shared session
    save_svg(elements_svg_code, prefix="elements_svg", session_id=session_id)
    
    # Also save the edited PNG file to the shared session
    if edited_png_path and os.path.exists(edited_png_path):
        try:
            with open(edited_png_path, 'rb') as f:
                edited_png_data = f.read()
            edited_png_base64 = base64.b64encode(edited_png_data).decode('utf-8')
            save_image(edited_png_base64, prefix="edited_png", session_id=session_id)
            logger.info(f"✅ Edited PNG saved to shared session: {session_id}")
        except Exception as e:
            logger.warning(f"Failed to save edited PNG to shared session: {e}")
    
    return elements_svg_code, elements_svg_path, edited_png_path

def ai_combine_svgs_with_session(text_svg_code, elements_svg_code, background_image_url, session_id):
    """Normal combination with session saving (no AI dependency)"""
    combined_svg = normal_combine_svgs(text_svg_code, elements_svg_code, background_image_url)
    # Save to shared session
    save_svg(combined_svg, prefix="combined_svg", session_id=session_id)
    return combined_svg

def post_process_svg_remove_first_path_with_session(svg_code, session_id):
    """Post-process SVG and save to shared session"""
    processed_svg = post_process_svg_remove_first_path(svg_code)
    # Save to shared session
    save_svg(processed_svg, prefix="final_svg", session_id=session_id)
    return processed_svg

def ai_fix_svg_with_png(elements_svg_code, elements_png_url, prompt=None):
    """Use an AI model to fix the SVG so it matches the PNG as closely as possible, including element and text positions and sizes."""
    logger.info("Starting AI-based SVG correction using PNG reference...")
    # Use OpenAI or Gemini vision model to compare and fix SVG
    # We'll use the PNG public URL and SVG code as input
    system_prompt = (
        "You are an expert SVG repair assistant. "
        "Given an SVG code and a PNG image (URL), your job is to edit the SVG so it visually matches the PNG as closely as possible. "
        "Fix missing elements, colors, shapes, text, and details. "
        "Most importantly, ensure that the position and size of each element and all text in the SVG matches the corresponding element and text in the PNG as closely as possible. "
        "Do not just match colors and shapes, but also their exact placement, proportions, and text positioning. "
        "Return ONLY the corrected SVG code."
    )
    user_prompt = f"""
Here is the current SVG code:
```svg
{elements_svg_code}
```

Here is the PNG image (URL):
{elements_png_url}

{('Original prompt: ' + prompt) if prompt else ''}

Please return the corrected SVG code that matches the PNG as closely as possible, including element and text positions and sizes. Only output SVG code.
"""
    # Use OpenRouter Gemini if available, else fallback to OpenAI
    ai_response = optimized_openrouter_call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model="google/gemini-2.5-flash",
        max_tokens=64000,
        temperature=1
    )
    if ai_response and '<svg' in ai_response:
        logger.info("AI-based SVG correction successful.")
        return ai_response
    logger.warning("AI-based SVG correction failed or did not return SVG. Returning original SVG.")
    return elements_svg_code


if __name__ == '__main__':
    # Get port from environment variable (Render sets PORT=8000)
    port = int(os.getenv('PORT', 5000))
    
    # Use 0.0.0.0 for production (Render) and 127.0.0.1 for local development
    host = '0.0.0.0' if os.getenv('PORT') else '127.0.0.1'
    
    # Disable debug mode in production
    debug = not bool(os.getenv('PORT'))
    
    logger.info(f"Starting Flask application on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)