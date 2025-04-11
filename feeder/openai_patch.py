import os
import logging
import openai
import importlib

logger = logging.getLogger(__name__)

def patch_openai():
    """
    Patch the OpenAI library to fix the 'proxies' parameter issue.
    This is needed because some environment or configuration is causing
    the OpenAI client to receive a 'proxies' parameter that it doesn't accept.
    """
    logger.info("Patching OpenAI library...")
    
    # Get the API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set!")
        return False
        
    try:
        # Try to patch the module client creation
        from openai import _base_client
        
        # Store the original SyncHttpxClientWrapper.__init__ function
        original_init = _base_client.SyncHttpxClientWrapper.__init__
        
        # Define a patched version that removes the 'proxies' parameter
        def patched_init(self, *args, **kwargs):
            if 'proxies' in kwargs:
                logger.info("Removing 'proxies' parameter from OpenAI client initialization")
                del kwargs['proxies']
            return original_init(self, *args, **kwargs)
        
        # Replace the original __init__ with our patched version
        _base_client.SyncHttpxClientWrapper.__init__ = patched_init
        
        # Set the API key on the module
        openai.api_key = api_key
        
        logger.info("OpenAI library patched successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to patch OpenAI library: {str(e)}")
        return False
        
# Alternative approach - create a custom client wrapper
class OpenAIClientWrapper:
    """
    A simple wrapper around direct module-level OpenAI API calls.
    This avoids using the OpenAI client object which has the proxy issues.
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.error("OPENAI_API_KEY environment variable not set!")
            
        # Set the API key directly on the module
        openai.api_key = self.api_key
        
        # Create interfaces for the different API endpoints
        self.chat = ChatCompletionsWrapper()
        self.embeddings = EmbeddingsWrapper()
        
        logger.info("OpenAI client wrapper initialized")
        

class ChatCompletionsWrapper:
    def create(self, **kwargs):
        """Wrapper around openai.chat.completions.create"""
        logger.debug("Using module-level OpenAI chat completions")
        return openai.chat.completions.create(**kwargs)


class EmbeddingsWrapper:
    def create(self, **kwargs):
        """Wrapper around openai.embeddings.create"""
        logger.debug("Using module-level OpenAI embeddings")
        return openai.embeddings.create(**kwargs) 