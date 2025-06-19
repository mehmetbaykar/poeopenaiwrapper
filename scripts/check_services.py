#!/usr/bin/env python
# pylint: disable=import-error
"""Check service availability utilities."""
import sys
import time

import requests


def check_health():
    """Check if the POE wrapper service is healthy"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def wait_for_service(max_wait=30):
    """Wait for service to be ready"""
    print("⏳ Waiting for services to start...")

    for _ in range(max_wait):
        if check_health():
            print("✅ POE Wrapper service is healthy")
            return True
        time.sleep(1)

    print("⚠️ POE Wrapper service may not be ready yet")
    return False

if __name__ == "__main__":
    success = wait_for_service()
    sys.exit(0 if success else 1)
