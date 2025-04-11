#!/usr/bin/env python3

import os
import sys
import argparse
import time
import signal
import logging
from dotenv import load_dotenv

# Add the parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from feeder.logging_config import configure_logging
from feeder.models import init_db
from feeder.scheduler import run_pipeline, start_scheduler

# Configure logging before anything else
configure_logging()
logger = logging.getLogger(__name__)

# Load environment variables with detailed logging
logger.info("Loading environment variables")
load_dotenv()
logger.info("Environment variables loaded")

# Log all environment variables for debugging (excluding sensitive ones)
for key, value in os.environ.items():
    if key != "OPENAI_API_KEY" and not key.lower().startswith("password") and not key.lower().startswith("secret"):
        logger.debug(f"Environment variable: {key}={value}")
    else:
        logger.debug(f"Environment variable: {key}=[REDACTED]")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="RSS Feed Aggregator and Analyzer")
    
    parser.add_argument(
        "--run", 
        action="store_true", 
        help="Run the pipeline once and exit"
    )
    
    parser.add_argument(
        "--schedule", 
        action="store_true", 
        help="Run the pipeline on a schedule (default)"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        help="Schedule interval in hours (overrides environment variable)"
    )
    
    args = parser.parse_args()
    
    # If no arguments provided, default to scheduled mode
    if not args.run and not args.schedule:
        args.schedule = True
    
    return args


def handle_exit(signum, frame):
    """Handle exit signals gracefully."""
    logger.info("Received signal to terminate. Shutting down...")
    sys.exit(0)


def main():
    """Main entry point for the application."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    # Parse command line arguments
    args = parse_args()
    
    # Update environment variable if interval specified
    if args.interval:
        os.environ["SCHEDULE_INTERVAL"] = str(args.interval)
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        
        if args.run:
            # Run once
            logger.info("Running pipeline once...")
            run_pipeline()
            logger.info("Pipeline execution complete.")
            
        elif args.schedule:
            # Run on schedule
            interval = int(os.getenv("SCHEDULE_INTERVAL", "1"))
            logger.info(f"Starting scheduler to run every {interval} hour(s)...")
            
            # Run immediately
            logger.info("Running initial pipeline execution...")
            run_pipeline()
            
            # Start scheduler
            scheduler = start_scheduler()
            
            try:
                # Keep the main thread alive
                logger.info("Press Ctrl+C to exit")
                while True:
                    time.sleep(60)
            except (KeyboardInterrupt, SystemExit):
                logger.info("Shutting down scheduler...")
                scheduler.shutdown()
                logger.info("Scheduler stopped.")
    
    except Exception as e:
        logger.error(f"Error in main application: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 