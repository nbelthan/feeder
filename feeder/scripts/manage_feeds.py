#!/usr/bin/env python3

import os
import sys
import argparse
from typing import List, Dict

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from feeder.models import Session, Feed, init_db
from feeder.feed_processor import fetch_feeds
from dotenv import load_dotenv

load_dotenv()


def list_feeds() -> None:
    """List all feeds in the database."""
    session = Session()
    try:
        feeds = session.query(Feed).order_by(Feed.name).all()
        
        if not feeds:
            print("No feeds found in the database.")
            return
        
        print(f"Found {len(feeds)} feeds:")
        print("-" * 80)
        print(f"{'ID':<5} {'Active':<8} {'Name':<30} {'URL':<40}")
        print("-" * 80)
        
        for feed in feeds:
            status = "✓" if feed.active else "✗"
            print(f"{feed.id:<5} {status:<8} {feed.name[:28]:<30} {feed.url[:38]:<40}")
    
    finally:
        session.close()


def add_feed(name: str, url: str) -> None:
    """
    Add a new feed to the database.
    
    Args:
        name: Feed name
        url: Feed URL
    """
    session = Session()
    try:
        # Check if feed already exists
        existing = session.query(Feed).filter(Feed.url == url).first()
        if existing:
            print(f"Feed with URL '{url}' already exists with name '{existing.name}'.")
            return
        
        # Create new feed
        feed = Feed(name=name, url=url, active=True)
        session.add(feed)
        session.commit()
        
        print(f"Added feed: {name} ({url})")
    
    except Exception as e:
        session.rollback()
        print(f"Error adding feed: {str(e)}")
    
    finally:
        session.close()


def remove_feed(feed_id: int) -> None:
    """
    Remove a feed from the database.
    
    Args:
        feed_id: Feed ID to remove
    """
    session = Session()
    try:
        # Find the feed
        feed = session.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            print(f"Feed with ID {feed_id} not found.")
            return
        
        # Confirm
        print(f"About to remove feed: {feed.name} ({feed.url})")
        confirm = input("Are you sure? (y/n): ").lower()
        
        if confirm != 'y':
            print("Operation cancelled.")
            return
        
        # Delete the feed
        session.delete(feed)
        session.commit()
        
        print(f"Removed feed: {feed.name}")
    
    except Exception as e:
        session.rollback()
        print(f"Error removing feed: {str(e)}")
    
    finally:
        session.close()


def toggle_feed(feed_id: int, activate: bool) -> None:
    """
    Activate or deactivate a feed.
    
    Args:
        feed_id: Feed ID to toggle
        activate: True to activate, False to deactivate
    """
    session = Session()
    try:
        # Find the feed
        feed = session.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            print(f"Feed with ID {feed_id} not found.")
            return
        
        # Update status
        feed.active = activate
        session.add(feed)
        session.commit()
        
        status = "activated" if activate else "deactivated"
        print(f"Feed '{feed.name}' {status}.")
    
    except Exception as e:
        session.rollback()
        print(f"Error updating feed: {str(e)}")
    
    finally:
        session.close()


def test_feed(url: str) -> None:
    """
    Test a feed URL without adding it to the database.
    
    Args:
        url: Feed URL to test
    """
    import feedparser
    
    print(f"Testing feed URL: {url}")
    
    # Parse the feed
    feed_data = feedparser.parse(url)
    
    # Check for errors
    if hasattr(feed_data, 'bozo_exception'):
        print(f"Error: {feed_data.bozo_exception}")
        return
    
    # Check if feed has entries
    if not hasattr(feed_data, 'entries') or not feed_data.entries:
        print("Feed parsed successfully but contains no entries.")
        return
    
    # Get feed title
    title = feed_data.feed.title if hasattr(feed_data.feed, 'title') else "Unknown"
    
    # Print info
    print(f"Feed title: {title}")
    print(f"Number of entries: {len(feed_data.entries)}")
    
    # Print some sample entries
    print("\nSample entries:")
    for i, entry in enumerate(feed_data.entries[:3]):
        print(f"  {i+1}. {getattr(entry, 'title', 'Untitled')}")
        if hasattr(entry, 'published'):
            print(f"     Published: {entry.published}")
    
    print("\nFeed test successful!")


def update_feeds() -> None:
    """Fetch updates from all active feeds."""
    print("Fetching updates from all active feeds...")
    
    # Run the fetch_feeds function
    new_articles = fetch_feeds()
    
    print(f"Fetched {new_articles} new articles.")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Manage RSS feeds in the database")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List feeds
    list_parser = subparsers.add_parser("list", help="List all feeds")
    
    # Add feed
    add_parser = subparsers.add_parser("add", help="Add a new feed")
    add_parser.add_argument("name", help="Feed name")
    add_parser.add_argument("url", help="Feed URL")
    
    # Remove feed
    remove_parser = subparsers.add_parser("remove", help="Remove a feed")
    remove_parser.add_argument("feed_id", type=int, help="Feed ID to remove")
    
    # Activate feed
    activate_parser = subparsers.add_parser("activate", help="Activate a feed")
    activate_parser.add_argument("feed_id", type=int, help="Feed ID to activate")
    
    # Deactivate feed
    deactivate_parser = subparsers.add_parser("deactivate", help="Deactivate a feed")
    deactivate_parser.add_argument("feed_id", type=int, help="Feed ID to deactivate")
    
    # Test feed
    test_parser = subparsers.add_parser("test", help="Test a feed URL without adding it")
    test_parser.add_argument("url", help="Feed URL to test")
    
    # Update feeds
    update_parser = subparsers.add_parser("update", help="Fetch updates from all active feeds")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Initialize the database
    init_db()
    
    # Run the appropriate command
    if args.command == "list":
        list_feeds()
    elif args.command == "add":
        add_feed(args.name, args.url)
    elif args.command == "remove":
        remove_feed(args.feed_id)
    elif args.command == "activate":
        toggle_feed(args.feed_id, True)
    elif args.command == "deactivate":
        toggle_feed(args.feed_id, False)
    elif args.command == "test":
        test_feed(args.url)
    elif args.command == "update":
        update_feeds()
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 