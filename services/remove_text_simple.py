#!/usr/bin/env python3
import os
import base64
import requests
import replicate
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up API tokens from environment
replicate_key = os.getenv('REPLICATE_API_KEY')
if replicate_key:
    os.environ['REPLICATE_API_TOKEN'] = replicate_key

# Set up OpenAI API key
openai_api_key = os.getenv('OPENAI_API_KEY_SVG') or os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("OpenAI API key must be set in environment variables")

def analyze_image_with_gpt4o_mini(image_base64: str) -> str:
    """Use GPT-4o-mini to analyze image and generate detailed removal prompt"""
    print("🧠 Analyzing image with GPT-4o-mini to generate optimal removal prompt...")
    
    system_prompt = """🧠 System Prompt for Training an Image Editing Instruction Generator AI
You are a highly skilled image editing instruction generator AI.

Your job is to analyze the user's request along with the provided image, and generate a clear, detailed, and precise prompt for an image editing model.

You must:
- Refer to visual elements by their position and appearance (e.g., "centered black text", "red floral shape in the top-left corner")
- Clearly list what to remove, what to retain, and what to change
- Include expected output details (e.g., transparency, output format, background)
- Use professional and concise formatting
- Never assume or hallucinate any changes not requested by the user

Generate a detailed prompt for Flux that will remove ALL text and ALL background elements, keeping ONLY the main graphic objects/shapes/elements isolated on a clean background."""

    user_prompt = """Analyze this image and generate a detailed prompt for an AI image editing model (Flux) that will:

1. Remove ALL text content from the image
2. Remove ALL background elements, colors, patterns, and textures  
3. Keep ONLY the main graphic objects, shapes, and visual elements
4. Output should have elements isolated on a clean/transparent background

Please provide a specific, detailed prompt that describes exactly what to remove and what to keep, referencing the visual elements by their position, color, and appearance."""

    try:
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        generated_prompt = response.choices[0].message.content
        print(f"✅ Generated detailed prompt: {generated_prompt[:100]}...")
        return generated_prompt
        
    except Exception as e:
        print(f"⚠️ GPT-4o-mini analysis failed: {str(e)}")
        # Fallback to default prompt
        fallback_prompt = (
            "Remove all text and all background from this image. Keep ONLY the main objects, elements, shapes, and graphic components. "
            "Make the background completely transparent or white. Remove all text, all background colors, all background patterns, "
            "all background textures, and all background elements. Extract only the essential visual elements and objects, "
            "leaving them isolated without any background or text. The result should show only the core graphic elements "
            "on a clean, transparent or white background with no text whatsoever."
        )
        print(f"🔄 Using fallback prompt due to analysis failure")
        return fallback_prompt

def remove_text(input_image_path: str) -> str:
    """Use Replicate Flux to remove both text AND background from the image, keeping only elements"""
    print("Processing image with Replicate Flux...")
    
    try:
        # Convert image to base64 for upload
        with open(input_image_path, "rb") as image_file:
            image_data = image_file.read()
        
        # Convert image data to base64 for Flux input
        input_image_base64 = base64.b64encode(image_data).decode('utf-8')
        input_image_data_url = f"data:image/png;base64,{input_image_base64}"
        
        # Step 1: Use GPT-4o-mini to analyze image and generate detailed removal prompt
        print("🔍 Step 1: Analyzing image with GPT-4o-mini...")
        detailed_prompt = analyze_image_with_gpt4o_mini(input_image_base64)
        
        # Step 2: Use the generated prompt with Flux for precise editing
        print("🎨 Step 2: Applying edits with Flux Kontext Pro...")
        prompt = detailed_prompt
        
        # Use Flux Kontext Pro with input image for text and background removal
        output = replicate.run(
            "black-forest-labs/flux-kontext-pro",
            input={
                "prompt": prompt,
                "input_image": input_image_data_url,
                "aspect_ratio": "match_input_image",
                "output_format": "jpg",
                "safety_tolerance": 2,
                "prompt_upsampling": False
            }
        )
        
        # Download the generated image
        image_url = str(output[0]) if isinstance(output, list) else str(output)
        response = requests.get(image_url)
        
        # Save the result
        timestamp = os.path.splitext(os.path.basename(input_image_path))[0]
        output_path = f"edited_{timestamp}.png"
        
        # Save the image
        with open(output_path, "wb") as f:
            f.write(response.content)
            
        print(f"✓ Saved edited image to {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Error calling Replicate API: {str(e)}")
        raise

def main():
    # Use the specified image path
    input_image = "gpt_image_20250608_152538_e02c5414.png"
    
    if not os.path.exists(input_image):
        print(f"❌ Error: Image not found at {input_image}")
        return
        
    try:
        # Remove text from the image
        output_path = remove_text(input_image)
        
        print("\n✨ All done! Process completed successfully:")
        print(f"Input image: {input_image}")
        print(f"Final output: {output_path}")
        
    except Exception as e:
        print(f"\n❌ Process failed: {str(e)}")

if __name__ == "__main__":
    main() 