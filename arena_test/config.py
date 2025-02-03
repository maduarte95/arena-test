from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get API key, with error handling
def get_api_key():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables. Please check your .env file.")
    return api_key

