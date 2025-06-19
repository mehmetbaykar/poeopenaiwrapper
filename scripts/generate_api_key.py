#!/usr/bin/env python
# pylint: disable=import-error
"""Generate a random API key."""
import secrets
import string


def generate_api_key(length=64):
    """Generate a secure API key"""
    alphabet = string.ascii_letters + string.digits
    return 'sk-local-' + ''.join(secrets.choice(alphabet) for _ in range(length))

def main() -> None:
    """Entry point for script."""
    api_key = generate_api_key()
    print(api_key)


if __name__ == "__main__":
    main()
