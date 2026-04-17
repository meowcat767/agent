import os
from dotenv import load_dotenv

def verify():
    print("--- Setup Verification ---")
    
    # Check if .env.example exists
    if os.path.exists(".env.example"):
        print("[OK] .env.example exists.")
    else:
        print("[FAIL] .env.example missing.")

    # Check for venv
    if os.path.exists("venv"):
        print("[OK] Virtual environment (venv) exists.")
    else:
        print("[FAIL] Virtual environment (venv) missing.")

    # Check for agent.py
    if os.path.exists("agent.py"):
        print("[OK] agent.py exists.")
    else:
        print("[FAIL] agent.py missing.")

    # Check dependencies
    try:
        import groq
        import dotenv
        import duckduckgo_search
        import requests
        print("[OK] Dependencies (groq, python-dotenv, duckduckgo_search, requests) are installed.")
    except ImportError as e:
        print(f"[FAIL] Dependency missing: {e}")

    # Check .env
    load_dotenv()
    if os.getenv("GIT_USERNAME") and os.getenv("GIT_TOKEN"):
        print("[OK] Git credentials found in .env.")
    else:
        print("[INFO] Git credentials not fully configured in .env.")

if __name__ == "__main__":
    verify()
