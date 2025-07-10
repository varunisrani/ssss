#!/usr/bin/env python3
"""
Setup script for Jaaz server environment configuration
This script helps configure the GPT-image-1 model and other providers
"""

import os
import shutil
import sys
from pathlib import Path

def setup_environment():
    """Setup the environment files and directories"""
    
    server_dir = Path(__file__).parent
    
    # Create user_data directory if it doesn't exist
    user_data_dir = server_dir / "user_data"
    user_data_dir.mkdir(exist_ok=True)
    print(f"✓ Created user_data directory: {user_data_dir}")
    
    # Create config.toml from example if it doesn't exist
    config_file = user_data_dir / "config.toml"
    config_example = server_dir / "config.toml.example"
    
    if not config_file.exists() and config_example.exists():
        shutil.copy(config_example, config_file)
        print(f"✓ Created config.toml from example: {config_file}")
        print("  Please edit config.toml to add your API keys")
    elif config_file.exists():
        print(f"✓ Config file already exists: {config_file}")
    
    # Create files directory for uploads
    files_dir = user_data_dir / "files"
    files_dir.mkdir(exist_ok=True)
    print(f"✓ Created files directory: {files_dir}")
    
    # Check for .env file
    env_file = server_dir / ".env"
    if env_file.exists():
        print(f"✓ Environment file exists: {env_file}")
    else:
        print(f"⚠ No .env file found at: {env_file}")
    
    return True

def check_config():
    """Check if GPT-image-1 model is properly configured"""
    
    server_dir = Path(__file__).parent
    config_file = server_dir / "user_data" / "config.toml"
    
    if not config_file.exists():
        print("❌ config.toml not found. Run setup_environment() first.")
        return False
    
    try:
        import toml
        config = toml.load(config_file)
        
        # Check for Jaaz provider
        jaaz_configured = False
        if 'jaaz' in config and config['jaaz'].get('api_key'):
            jaaz_configured = True
            print("✓ Jaaz provider configured with API key")
        
        # Check for OpenAI provider
        openai_configured = False
        if 'openai' in config and config['openai'].get('api_key'):
            openai_configured = True
            print("✓ OpenAI provider configured with API key")
        
        if jaaz_configured or openai_configured:
            print("✓ GPT-image-1 model should be available")
            return True
        else:
            print("❌ No API keys configured for GPT-image-1 model")
            print("   Please add either 'jaaz.api_key' or 'openai.api_key' to config.toml")
            return False
            
    except ImportError:
        print("❌ toml library not installed. Run: pip install toml")
        return False
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        return False

def main():
    """Main setup function"""
    
    print("=== Jaaz Server Environment Setup ===")
    print()
    
    # Setup environment
    print("1. Setting up environment...")
    setup_environment()
    print()
    
    # Check configuration
    print("2. Checking configuration...")
    config_ok = check_config()
    print()
    
    # Print next steps
    print("=== Next Steps ===")
    
    if not config_ok:
        print("1. Edit user_data/config.toml and add your API keys:")
        print("   - For Jaaz provider: add 'api_key' under [jaaz] section")
        print("   - For OpenAI provider: add 'api_key' under [openai] section")
        print()
        print("2. Get API keys from:")
        print("   - Jaaz: https://www.jaaz.app/dashboard")
        print("   - OpenAI: https://platform.openai.com/api-keys")
        print()
    
    print("3. Start the server:")
    print("   python main.py")
    print()
    
    print("4. The GPT-image-1 model will be available as:")
    print("   - Tool: generate_image_by_gpt_image_1_jaaz")
    print("   - Model: openai/gpt-image-1")
    print("   - Provider: jaaz")
    print("   - Features: Multiple input images, aspect ratios, prompt-based generation")
    print()

if __name__ == "__main__":
    main()