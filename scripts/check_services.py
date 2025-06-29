"""
Script to check the health of the POE wrapper service.
"""

import sys
import time

import requests

def check_health() -> bool:
    """Checks if the POE wrapper service is healthy by making an HTTP GET request."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def wait_for_service(max_wait: int = 30) -> bool:
    """Waits for the POE wrapper service to become healthy."""
    print("⏳ Waiting for services to start...")

    for _ in range(max_wait):
        if check_health():
            print("✅ POE Wrapper service is healthy")
            return True
        time.sleep(1)

    print("⚠️ POE Wrapper service may not be ready yet")
    return False


if __name__ == "__main__":
    if wait_for_service():
        sys.exit(0)
    else:
        sys.exit(1)
