#!/usr/bin/env python3
import os
import uuid
import vtracer
from datetime import datetime

def convert_png_to_svg(input_image_path):
    """Convert PNG to SVG using vtracer with optimized settings"""
    print(f"Converting {input_image_path} to SVG...")
    
    try:
        # Generate output path for SVG
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_svg = f"traced_{timestamp}_{uuid.uuid4()}.svg"
        
        # Convert image to SVG using vtracer with optimized settings
        vtracer.convert_image_to_svg_py(
            input_image_path,
            output_svg,
            colormode='color',         # Use color mode for richer output
            hierarchical='stacked',    # Use stacked mode for better layering
            mode='spline',            # Use spline mode for smoother curves
            filter_speckle=8,         # ✅ Fewer layers - removes more details
            color_precision=4,        # ✅ Fewer layers - merges similar colors
            layer_difference=48,      # ✅ Fewer layers - higher difference threshold
            corner_threshold=80,      # ✅ Fewer layers - smoother corners
            length_threshold=6.0,     # ✅ Fewer layers - removes smaller elements
            max_iterations=8,         # ✅ Fewer layers - less optimization
            splice_threshold=60,      # ✅ Fewer layers - more aggressive merging
            path_precision=2          # ✅ Fewer layers - simpler paths
        )
        
        print(f"✓ Successfully converted image to SVG")
        print(f"✓ Saved as: {output_svg}")
        
        return output_svg
        
    except Exception as e:
        print(f"❌ Error in SVG conversion: {str(e)}")
        raise

def main():
    # Input image path
    input_image = "edited_ChatGPT Image Jun 8, 2025, 04_35_06 AM.png"
    
    if not os.path.exists(input_image):
        print(f"❌ Error: Image not found at {input_image}")
        return
        
    try:
        # Convert PNG to SVG
        svg_path = convert_png_to_svg(input_image)
        
        print("\n✨ All done! Process completed successfully:")
        print(f"Input image: {input_image}")
        print(f"Output SVG: {svg_path}")
        
    except Exception as e:
        print(f"\n❌ Process failed: {str(e)}")

if __name__ == "__main__":
    main() 