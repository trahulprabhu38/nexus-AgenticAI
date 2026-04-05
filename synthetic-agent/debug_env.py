import os
from dotenv import load_dotenv

# Load root .env
root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(root_path, ".env")
load_dotenv(env_path)

print(f"Env Path: {env_path}")
print(f"File Exists: {os.path.exists(env_path)}")
print(f"DB URL Set: {bool(os.getenv('AIML_RESULTS_DATABASE_URL'))}")
print(f"Key Set: {bool(os.getenv('NVIDIA_API_KEY'))}")
