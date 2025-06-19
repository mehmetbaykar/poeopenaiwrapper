#!/usr/bin/env python
# pylint: disable=import-error
"""Environment file creation helper."""
import sys


def create_env_file(poe_key, local_key, ngrok_token):
    """Create .env file with provided values"""

    env_content = f"""# POE API Configuration
POE_API_KEY={poe_key}

# Local API Configuration
LOCAL_API_KEY={local_key}

# Ngrok Configuration
NGROK_AUTHTOKEN={ngrok_token}

# Server Configuration
PORT=8000
WORKERS=1
LOG_LEVEL=info
MAX_FILE_SIZE_MB=50

# Optional Features
ENABLE_HEALTHCHECK=true
"""

    try:
        with open('.env', 'w', encoding='utf-8') as env_file:
            env_file.write(env_content)
        print("✅ .env file created successfully")
        return True
    except OSError as e:
        print(f"❌ Error creating .env file: {e}")
        return False


def main() -> None:
    """Entry point for script."""
    if len(sys.argv) != 4:
        print("Usage: python create_env.py <poe_api_key> <local_api_key> <ngrok_authtoken>")
        sys.exit(1)

    poe_key = sys.argv[1]
    local_key = sys.argv[2]
    ngrok_token = sys.argv[3]

    success = create_env_file(poe_key, local_key, ngrok_token)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
