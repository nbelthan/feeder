import feedparser
import datetime
from dateutil import parser as date_parser
from newspaper import Article as NewspaperArticle
import logging
from sqlalchemy import and_
from typing import List, Optional
import time

from feeder.models import Session, Feed, Article

logger = logging.getLogger(__name__)


def fetch_feeds(session: Optional[Session] = None) -> int:
    """
    Fetch all active RSS feeds and store new articles in the database.
    
    Args:
        session: SQLAlchemy session. If None, a new session will be created.
        
    Returns:
        Number of new articles added to the database.
    """
    close_session = False
    if session is None:
        session = Session()
        close_session = True
    
    try:
        feeds = session.query(Feed).filter(Feed.active == True).all()
        logger.info(f"Fetching {len(feeds)} active feeds")
        
        new_article_count = 0
        
        for feed in feeds:
            try:
                # Fetch the feed
                feed_data = feedparser.parse(feed.url)
                
                # Check for errors
                if hasattr(feed_data, 'bozo_exception'):
                    logger.error(f"Error fetching feed {feed.name}: {feed_data.bozo_exception}")
                    continue
                
                # Process entries
                for entry in feed_data.entries:
                    # Try to get URL
                    url = getattr(entry, 'link', None)
                    if not url:
                        continue
                    
                    # Check if article already exists
                    existing = session.query(Article).filter(Article.url == url).first()
                    if existing:
                        continue
                    
                    # Get published date
                    published_at = None
                    if hasattr(entry, 'published'):
                        try:
                            published_at = date_parser.parse(entry.published)
                        except:
                            pass
                    
                    # Get title
                    title = getattr(entry, 'title', 'Untitled')
                    
                    # Get author
                    author = None
                    if hasattr(entry, 'author'):
                        author = entry.author
                    
                    # Get summary
                    summary = None
                    if hasattr(entry, 'summary'):
                        summary = entry.summary
                    
                    # Create new article
                    article = Article(
                        feed_id=feed.id,
                        title=title,
                        url=url,
                        published_at=published_at,
                        author=author,
                        summary=summary,
                        content_extracted=False,
                        analyzed=False
                    )
                    
                    session.add(article)
                    new_article_count += 1
                
                # Update last_fetched timestamp
                feed.last_fetched = datetime.datetime.utcnow()
                session.commit()
                
            except Exception as e:
                logger.error(f"Error processing feed {feed.name}: {str(e)}")
                session.rollback()
        
        if new_article_count > 0:
            logger.info(f"Added {new_article_count} new articles to the database")
        
        return new_article_count
        
    finally:
        if close_session:
            session.close()


def extract_content(max_articles: int = 10, session: Optional[Session] = None) -> int:
    """
    Extract content from articles that haven't been processed yet.
    
    Args:
        max_articles: Maximum number of articles to process
        session: SQLAlchemy session. If None, a new session will be created.
        
    Returns:
        Number of articles successfully processed.
    """
    close_session = False
    if session is None:
        session = Session()
        close_session = True
    
    try:
        # Get articles that need content extraction
        articles = session.query(Article).filter(
            and_(
                Article.content_extracted == False,
                Article.content == None
            )
        ).limit(max_articles).all()
        
        logger.info(f"Extracting content from {len(articles)} articles")
        
        processed_count = 0
        
        for article in articles:
            try:
                # Use newspaper3k to extract content
                news_article = NewspaperArticle(article.url)
                news_article.download()
                time.sleep(1)  # Be nice to the servers
                
                # Parse the article
                news_article.parse()
                
                # Update the article
                article.content = news_article.text
                
                # If we didn't have a summary before, use newspaper's
                if not article.summary and news_article.summary:
                    article.summary = news_article.summary
                
                # If we didn't have an author before, use newspaper's
                if not article.author and news_article.authors:
                    article.author = ', '.join(news_article.authors)
                
                # Mark as extracted
                article.content_extracted = True
                
                session.add(article)
                processed_count += 1
                
                # Commit every few articles to avoid large transactions
                if processed_count % 5 == 0:
                    session.commit()
                
            except Exception as e:
                logger.error(f"Error extracting content from {article.url}: {str(e)}")
                # Still mark as processed to avoid repeated failures
                article.content_extracted = True
                session.add(article)
        
        # Final commit
        session.commit()
        
        if processed_count > 0:
            logger.info(f"Successfully extracted content from {processed_count} articles")
        
        return processed_count
        
    finally:
        if close_session:
            session.close()


def get_unprocessed_articles(session: Optional[Session] = None) -> List[Article]:
    """
    Get articles that have content but haven't been analyzed yet.
    
    Args:
        session: SQLAlchemy session. If None, a new session will be created.
        
    Returns:
        List of articles ready for analysis.
    """
    close_session = False
    if session is None:
        session = Session()
        close_session = True
    
    try:
        articles = session.query(Article).filter(
            and_(
                Article.content_extracted == True,
                Article.content != None,
                Article.analyzed == False
            )
        ).all()
        
        return articles
        
    finally:
        if close_session:
            session.close() 