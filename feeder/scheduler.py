import os
import logging
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from feeder.models import Session
from feeder.feed_processor import fetch_feeds, extract_content
from feeder.analyzer import analyze_batch
from feeder.clustering import cluster_articles
from feeder.news_brief import generate_news_brief

logger = logging.getLogger(__name__)


def run_pipeline():
    """Run the complete news processing pipeline."""
    session = Session()
    
    try:
        logger.info("Starting news processing pipeline")
        
        # Step 1: Fetch new articles from RSS feeds
        new_articles = fetch_feeds(session)
        logger.info(f"Fetched {new_articles} new articles")
        
        # Step 2: Extract content from unprocessed articles
        max_articles = 60  # Increased limit
        processed = extract_content(max_articles, session)
        logger.info(f"Extracted content from {processed} articles")
        
        # Step 3: Analyze articles using Google Gemini (Corrected comment)
        max_analyses = 60  # Increased limit
        analyzed = analyze_batch(max_analyses, session)
        logger.info(f"Analyzed {analyzed} articles")
        
        # Step 4: Cluster similar articles
        # Only cluster if we have enough new articles
        min_articles = 10  # Minimum articles needed for clustering
        cluster_result = cluster_articles(min_articles, session=session)
        
        if cluster_result.get("status") == "success":
            logger.info(f"Created {cluster_result.get('cluster_count')} clusters")
            
            # Step 5: Generate news brief
            output_file = generate_news_brief(
                run_id=cluster_result.get("run_id"),
                session=session
            )
            
            if output_file:
                logger.info(f"Generated news brief: {output_file}")
            else:
                logger.error("Failed to generate news brief")
        else:
            logger.info(f"Clustering not performed: {cluster_result.get('status')}")
        
        logger.info("Pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Error in pipeline: {str(e)}")
        session.rollback()
    finally:
        session.close()


def start_scheduler():
    """Start the background scheduler for periodic pipeline execution."""
    scheduler = BackgroundScheduler()
    
    # Get interval from environment (in hours), default to 1 hour
    interval_hours = int(os.getenv("SCHEDULE_INTERVAL", "1"))
    
    # Add job to run the pipeline
    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(hours=interval_hours),
        id='news_pipeline',
        name='Process news feeds and generate brief',
        replace_existing=True
    )
    
    # Start the scheduler
    scheduler.start()
    logger.info(f"Scheduler started. Pipeline will run every {interval_hours} hour(s)")
    
    return scheduler 