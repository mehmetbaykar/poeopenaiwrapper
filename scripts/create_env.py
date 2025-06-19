#!/usr/bin/env python
# pylint: disable=import-error
"""Environment file creation helper."""
import sys


def create_env_file(poe_api_key, local_api_key, ngrok_authtoken):
    """Create .env file with provided values"""

    env_content = f"""# POE API Configuration
POE_API_KEY={poe_api_key}

# Local API Configuration
LOCAL_API_KEY={local_api_key}

# Ngrok Configuration
NGROK_AUTHTOKEN={ngrok_authtoken}

# Server Configuration
PORT=8000
WORKERS=1
LOG_LEVEL=info
MAX_FILE_SIZE_MB=50

# Optional Features
ENABLE_HEALTHCHECK=true
"""

    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ .env file created successfully")
        return True
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python create_env.py <poe_api_key> <local_api_key> <ngrok_authtoken>")
        sys.exit(1)

    poe_api_key = sys.argv[1]
    local_api_key = sys.argv[2]
    ngrok_authtoken = sys.argv[3]

    success = create_env_file(poe_api_key, local_api_key, ngrok_authtoken)
    sys.exit(0 if success else 1)
