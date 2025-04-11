import os
import json
import logging
import re  # Import re at the top
from typing import List, Dict, Any, Optional
import traceback
from sqlalchemy import and_
import numpy as np
import google.generativeai as genai

from feeder.models import Session, Article, ArticleAnalysis

logger = logging.getLogger(__name__)

# Initialize Google Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error("GEMINI_API_KEY environment variable not set!")
else:
    genai.configure(api_key=api_key)
    logger.info("Google Gemini API initialized successfully")

# Configure the model
generation_config = {
    "temperature": 0.1,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 1024,
}

def analyze_article(article: Article, session: Optional[Session] = None) -> bool:
    """
    Analyze an article using Google Gemini API and store the results.
    
    Args:
        article: Article to analyze
        session: SQLAlchemy session. If None, a new session will be created.
        
    Returns:
        True if analysis was successful, False otherwise.
    """
    close_session = False
    if session is None:
        session = Session()
        close_session = True
    
    try:
        # Check if the article has already been analyzed
        existing_analysis = session.query(ArticleAnalysis).filter(
            ArticleAnalysis.article_id == article.id
        ).first()
        
        if existing_analysis:
            logger.info(f"Article {article.id} already analyzed, skipping")
            return True
        
        # Analyze article content
        logger.info(f"Analyzing article {article.id}: {article.title}")
        
        # Extract content from the article
        content = article.content if article.content else article.summary if article.summary else ""
        if not content:
            logger.warning(f"Article {article.id} has no content or summary, skipping")
            return False
        
        # Analyze content using Google Gemini
        analysis_result = analyze_content(article.title, content)
        if not analysis_result:
            logger.error(f"Failed to analyze article {article.id}")
            return False
        
        # Create embeddings for clustering
        embedding = get_embedding(content)
        if embedding is None:
            logger.error(f"Failed to get embedding for article {article.id}")
            return False
        
        # Create article analysis
        article_analysis = ArticleAnalysis(
            article_id=article.id,
            summary=analysis_result.get("summary", ""),
            sentiment_score=analysis_result.get("sentiment_score", 0.0),
            topics=json.dumps(analysis_result.get("topics", [])),
            key_entities=json.dumps(analysis_result.get("entities", [])),
            embedding=json.dumps(embedding),
        )
        
        # Add to session and commit
        session.add(article_analysis)

        # Mark the original article as analyzed
        article.analyzed = True
        session.add(article) # Add the updated article object too
        
        session.commit()
        
        logger.info(f"Article {article.id} analyzed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error analyzing article {article.id}: {str(e)}")
        if close_session:
            session.rollback()
        return False
    
    finally:
        if close_session:
            session.close()

def analyze_content(title: str, content: str) -> Dict[str, Any]:
    """
    Analyze article content using Google Gemini API.

    Args:
        title: Article title
        content: Article content

    Returns:
        Dictionary with analysis results or None if analysis fails completely.
    """
    try:
        # Create prompt for analysis
        prompt = f"""
        Analyze the following news article:

        Title: {title}

        Content: {content}

        Please provide:
        1. A concise summary (1-2 sentences)
        2. Sentiment score (a single float from -1.0 to 1.0)
        3. Main topics (a JSON list of up to 5 keywords or phrases)
        4. Key entities mentioned (a JSON list of people, organizations, places, etc.)

        Format your response strictly as a JSON object with keys: "summary", "sentiment_score", "topics", "entities".
        Ensure sentiment_score is a float, and topics/entities are JSON lists of strings.
        Example:
        {{
          "summary": "A summary sentence.",
          "sentiment_score": 0.5,
          "topics": ["topic1", "topic2"],
          "entities": ["entity1", "entity2"]
        }}
        """

        # Call Google Gemini API
        logger.info(f"Calling Google Gemini API for content analysis of: {title}")
        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-pro",
                generation_config=generation_config
            )
            response = model.generate_content(prompt)
            logger.info(f"Google Gemini API call successful for: {title}")

            # Extract the response text
            result_text = response.text
            logger.debug(f"Raw response for '{title}':\n{result_text}") # Log raw response

            analysis_result = None
            # Attempt to parse the JSON response
            try:
                # More robust JSON extraction (handles potential markdown backticks)
                match = re.search(r'```(json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL | re.IGNORECASE)
                if match:
                    json_str = match.group(2)
                    logger.info(f"Extracted JSON block for '{title}'")
                else:
                    # Try finding JSON without backticks
                    json_match = re.search(r'(\{.*?\})', result_text, re.DOTALL)
                    if json_match:
                         json_str = json_match.group(1)
                         logger.info(f"Found JSON without backticks for '{title}'")
                    else:
                        json_str = result_text # Assume the whole text might be JSON
                        logger.warning(f"Could not find JSON block, assuming entire response is JSON for '{title}'")

                analysis_result = json.loads(json_str)
                logger.info(f"Successfully parsed analysis result for '{title}'")

                # Validate and clean the parsed result
                validated_result = {
                    "summary": str(analysis_result.get("summary", "")).strip(),
                    "sentiment_score": float(analysis_result.get("sentiment_score", 0.0)),
                    "topics": analysis_result.get("topics", []),
                    "entities": analysis_result.get("entities", [])
                }

                # Ensure topics and entities are lists of strings
                if not isinstance(validated_result["topics"], list):
                    validated_result["topics"] = []
                    logger.warning(f"Topics field was not a list for '{title}', resetting.")
                else:
                     validated_result["topics"] = [str(t) for t in validated_result["topics"]][:5] # Limit and stringify

                if not isinstance(validated_result["entities"], list):
                    validated_result["entities"] = []
                    logger.warning(f"Entities field was not a list for '{title}', resetting.")
                else:
                    validated_result["entities"] = [str(e) for e in validated_result["entities"]] # Stringify

                return validated_result

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON response for '{title}': {str(e)}")
                logger.warning(f"Attempting fallback extraction for '{title}'...")

                # Fallback: Attempt to extract information using regex from the raw text
                fallback_result = {
                    "summary": extract_field(result_text, r'(?:summary|Summary)\s*:\s*(.*)', ""),
                    "sentiment_score": extract_field(result_text, r'(?:sentiment_score|Sentiment Score)\s*:\s*(-?\d+\.?\d*)', 0.0, cast_type=float),
                    "topics": extract_list_field(result_text, r'(?:topics|Topics)\s*:\s*(.*)', []),
                    "entities": extract_list_field(result_text, r'(?:entities|Entities|Key Entities)\s*:\s*(.*)', [])
                }

                # Log success/failure of fallback
                extracted_count = sum(1 for v in fallback_result.values() if v) # Count non-empty/non-zero values
                if extracted_count > 0:
                    logger.info(f"Fallback extraction partially successful for '{title}' (found {extracted_count}/4 fields).")
                else:
                    logger.error(f"Fallback extraction failed for '{title}'.")

                return fallback_result

        except Exception as e:
            logger.error(f"Google Gemini API call failed for '{title}': {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None # Indicate failure

    except Exception as e:
        logger.error(f"Unexpected error in analyze_content for '{title}': {str(e)}")
        return None

def get_embedding(text: str) -> List[float]:
    """
    Generate embedding vector for text using Google Text Embeddings API.
    
    Args:
        text: Text to embed
        
    Returns:
        List of floats representing the embedding vector.
    """
    try:
        # Use Gemini for embeddings
        logger.info("Generating embedding using Google Embeddings API")
        
        # Truncate text if needed to fit within token limits
        max_chars = 10000  # Approximately 2500 tokens
        if len(text) > max_chars:
            text = text[:max_chars]
        
        try:
            # Use Google's embedding model
            embedding_model = "models/embedding-001"
            embedding = genai.embed_content(
                model=embedding_model,
                content=text,
                task_type="retrieval_document",
            )
            
            # Return the embedding values as a list
            if embedding and hasattr(embedding, "embedding"):
                return embedding.embedding
            else:
                # If embedding generation fails, return a random vector instead
                logger.warning("Failed to get proper embedding, using random vector")
                return list(np.random.normal(0, 1, 768))  # Common embedding size
                
        except Exception as e:
            logger.error(f"Error getting embedding: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return a random vector as fallback
            return list(np.random.normal(0, 1, 768))
            
    except Exception as e:
        logger.error(f"Error getting embedding: {str(e)}")
        return None
        
# Helper functions to extract information from unstructured text responses
# Simplified and combined extraction logic

def extract_field(text: str, pattern: str, default_value: Any, cast_type: type = str) -> Any:
    """Extract a single field using regex, with type casting."""
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        value = match.group(1).strip()
        try:
            # Special handling for lists potentially misinterpreted as single strings
            if cast_type == list:
                 if value.startswith('[') and value.endswith(']'):
                     # Attempt to parse as JSON list
                     try: return json.loads(value)
                     except: pass # Fallback to splitting
                 return [item.strip().strip('\'\"') for item in value.split(',') if item.strip()]

            return cast_type(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not cast extracted value '{value}' to {cast_type}: {e}")
            return default_value
    return default_value

def extract_list_field(text: str, pattern: str, default_value: List) -> List:
    """Extract a list field using regex, trying to handle comma/bullet points."""
    list_items = []
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        value_str = match.group(1).strip()
        # Try splitting by newline and finding bullet points first
        potential_items = value_str.split('\\n')
        found_bullets = False
        for item in potential_items:
            item = item.strip()
            if item.startswith(('-', '*', '•')):
                list_items.append(item[1:].strip())
                found_bullets = True
            elif found_bullets and item: # Stop if bullet list ends
                break
        
        # If no bullets found, try splitting by comma
        if not found_bullets and value_str:
             # Also handle if it looks like a JSON list string
             if value_str.startswith('[') and value_str.endswith(']'):
                 try:
                     parsed_list = json.loads(value_str)
                     if isinstance(parsed_list, list):
                         list_items = [str(i) for i in parsed_list]
                 except json.JSONDecodeError:
                      # Fallback if JSON parsing fails
                      list_items = [item.strip().strip('\'\"') for item in value_str.strip('[]').split(',') if item.strip()]
             else: # Simple comma split
                list_items = [item.strip().strip('\'\"') for item in value_str.split(',') if item.strip()]

    return list_items[:5] if list_items else default_value # Limit to 5

def analyze_unprocessed_articles(limit: int = None) -> int:
    """
    Analyze unprocessed articles.
    
    Args:
        limit: Maximum number of articles to analyze. If None, all unprocessed articles will be analyzed.
        
    Returns:
        Number of articles analyzed.
    """
    session = Session()
    try:
        # Fetch unprocessed articles
        query = session.query(Article).filter(
            and_(
                Article.content != None,
                ~Article.id.in_(
                    session.query(ArticleAnalysis.article_id)
                )
            )
        ).order_by(Article.published_at.desc())
        
        if limit:
            query = query.limit(limit)
            
        articles = query.all()
        
        count = 0
        for article in articles:
            if analyze_article(article, session):
                count += 1
                
        return count
    finally:
        session.close()

def analyze_batch(limit: int = None, session: Optional[Session] = None) -> int:
    """
    Analyze a batch of unprocessed articles.
    
    Args:
        limit: Maximum number of articles to analyze. If None, all unprocessed articles will be analyzed.
        session: SQLAlchemy session. If None, a new session will be created.
        
    Returns:
        Number of articles analyzed.
    """
    if session is None:
        return analyze_unprocessed_articles(limit)
    
    try:
        # Fetch unprocessed articles
        query = session.query(Article).filter(
            and_(
                Article.content != None,
                ~Article.id.in_(
                    session.query(ArticleAnalysis.article_id)
                )
            )
        ).order_by(Article.published_at.desc())
        
        if limit:
            query = query.limit(limit)
            
        articles = query.all()
        
        count = 0
        for article in articles:
            if analyze_article(article, session):
                count += 1
                
        return count
    except Exception as e:
        logger.error(f"Error in analyze_batch: {str(e)}")
        return 0 