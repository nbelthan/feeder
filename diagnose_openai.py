#!/usr/bin/env python3

import os
import sys
import openai
import json
import traceback
from dotenv import load_dotenv

# Load environment variables
print("Loading environment variables...")
load_dotenv()

# Get API key
api_key = os.getenv("OPENAI_API_KEY")
print(f"API key found: {'Yes' if api_key else 'No'}")

if not api_key:
    print("ERROR: OPENAI_API_KEY environment variable not set!")
    sys.exit(1)

# Print OpenAI package version
print(f"OpenAI package version: {openai.__version__}")

# Check for proxy environment variables
proxy_vars = {k: v for k, v in os.environ.items() if 'proxy' in k.lower()}
if proxy_vars:
    print(f"Found proxy environment variables that may cause issues:")
    for k, v in proxy_vars.items():
        print(f"  {k}={v}")

print("\n--- Testing direct API key method ---")
try:
    print("Setting API key directly on the module...")
    openai.api_key = api_key
    
    print("Making a simple completion request...")
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'hello world' for a test."}
        ]
    )
    
    content = response.choices[0].message.content
    print(f"Response content: {content}")
    print("Direct API key method SUCCESS")
except Exception as e:
    print(f"ERROR with direct API key method: {str(e)}")
    print(f"Exception type: {type(e).__name__}")
    print(f"Traceback: {traceback.format_exc()}")

print("\n--- Testing client object method ---")
try:
    print("Creating OpenAI client...")
    client = openai.OpenAI(api_key=api_key)
    
    print("Making a simple completion request with client...")
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'hello world' for a test with client."}
        ]
    )
    
    content = response.choices[0].message.content
    print(f"Response content: {content}")
    print("Client object method SUCCESS")
except Exception as e:
    print(f"ERROR with client object method: {str(e)}")
    print(f"Exception type: {type(e).__name__}")
    print(f"Traceback: {traceback.format_exc()}")

print("\n--- Attempting to inspect client initialization error ---")
try:
    # Try to create a client without arguments to see the default kwargs
    print("Creating default OpenAI client object to inspect arguments...")
    original_client = openai.OpenAI.__init__
    
    def patched_init(self, *args, **kwargs):
        print(f"OpenAI client init called with kwargs: {json.dumps(str(kwargs))}")
        return original_client(self, *args, **kwargs)
    
    openai.OpenAI.__init__ = patched_init
    client = openai.OpenAI()
    print("Default client creation SUCCESS")
except Exception as e:
    print(f"ERROR with patched client: {str(e)}")
    print(f"Exception type: {type(e).__name__}")
    print(f"Traceback: {traceback.format_exc()}")

print("\nDiagnostics complete. Check the output above for information on OpenAI API issues.") 