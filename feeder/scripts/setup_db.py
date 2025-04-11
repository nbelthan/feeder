#!/usr/bin/env python3

import os
import sys

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from feeder.models import init_db, Feed, Session
from dotenv import load_dotenv

load_dotenv()

SAMPLE_FEEDS = [
    {
        "name": "BBC News - World",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml"
    },
    {
        "name": "CNN - Top Stories",
        "url": "http://rss.cnn.com/rss/edition.rss"
    },
    {
        "name": "New York Times - Home Page",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
    },
    {
        "name": "Reuters - Top News",
        "url": "http://feeds.reuters.com/reuters/topNews"
    },
    {
        "name": "The Guardian - International",
        "url": "https://www.theguardian.com/world/rss"
    }
]


def setup_database():
    """Initialize the database and add sample feeds."""
    print("Initializing database...")
    init_db()
    
    session = Session()
    
    # Check if we already have feeds
    existing_feeds = session.query(Feed).count()
    if existing_feeds > 0:
        print(f"Database already contains {existing_feeds} feeds. Skipping sample feed creation.")
        session.close()
        return
    
    # Add sample feeds
    print("Adding sample RSS feeds...")
    for feed_data in SAMPLE_FEEDS:
        feed = Feed(name=feed_data["name"], url=feed_data["url"])
        session.add(feed)
    
    session.commit()
    print(f"Added {len(SAMPLE_FEEDS)} sample feeds.")
    session.close()


if __name__ == "__main__":
    setup_database()
    print("Database setup complete!") 