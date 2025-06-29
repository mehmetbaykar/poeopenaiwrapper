"""
Script to generate a secure API key.
"""

import secrets
import string


def generate_api_key(length: int = 64) -> str:
    """Generates a secure API key with a 'sk-local-' prefix."""
    alphabet = string.ascii_letters + string.digits
    return "sk-local-" + "".join(secrets.choice(alphabet) for _ in range(length))


if __name__ == "__main__":
    GENERATED_API_KEY = generate_api_key()
    print(GENERATED_API_KEY)
