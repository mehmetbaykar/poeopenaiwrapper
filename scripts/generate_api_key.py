#!/usr/bin/env python
import secrets
import string

def generate_api_key(length=64):
    """Generate a secure API key"""
    alphabet = string.ascii_letters + string.digits
    return 'sk-local-' + ''.join(secrets.choice(alphabet) for _ in range(length))

if __name__ == "__main__":
    api_key = generate_api_key()
    print(api_key)