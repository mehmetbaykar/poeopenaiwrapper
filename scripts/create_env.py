"""
Script to create or update the .env file for the application.
"""

import sys


def create_env_file(poe_api_key: str, local_api_key: str, ngrok_authtoken: str) -> bool:
    """Creates or updates the .env file with provided API keys and ngrok authtoken."""

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
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        print("✅ .env file created successfully")
        return True
    except IOError as e:
        print(f"❌ Error creating .env file: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python create_env.py <poe_api_key> <local_api_key> <ngrok_authtoken>")
        sys.exit(1)

    poe_key = sys.argv[1]
    local_key = sys.argv[2]
    ngrok_token = sys.argv[3]

    IS_SUCCESS = create_env_file(poe_key, local_key, ngrok_token)
    sys.exit(0 if IS_SUCCESS else 1)
