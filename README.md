# Feeder: RSS News Aggregator with AI Analysis

Feeder is an RSS news aggregator that automatically analyzes articles using Google's Gemini AI to generate concise news summaries and insights.

## Features

- Automatic RSS feed fetching and content extraction
- AI-powered analysis of news articles using Google Gemini
- Clustering of related articles to identify top stories
- Generation of a daily news brief with key insights
- Scheduled pipeline to keep your news brief up-to-date

## Setup

### Prerequisites

- Python 3.8 or later
- A Google Gemini API key ([Get one here](https://ai.google.dev/))
- SQLite (included with Python)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/feeder.git
   cd feeder
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables by copying the example file:
   ```
   cp .env.example .env
   ```

5. Edit the `.env` file to add your Google Gemini API key:
   ```
   # Google Gemini API Key for content analysis
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

### Adding RSS Feeds

Add RSS feeds to monitor using the management script:

```
python -m feeder.scripts.manage_feeds add "Feed Name" "https://example.com/rss.xml"
```

You can also list your current feeds:

```
python -m feeder.scripts.manage_feeds list
```

## Usage

### Run Once

To run the pipeline once and generate a news brief:

```
python run.py --run
```

This will:
1. Fetch new articles from your RSS feeds
2. Extract the content from each article
3. Analyze the content using Google Gemini
4. Cluster similar articles together
5. Generate a news brief in Markdown format (saved to `news_brief.md` by default)

### Run on Schedule

To run the pipeline continuously on an hourly schedule:

```
python run.py --schedule
```

You can configure the schedule interval in the `.env` file:

```
SCHEDULE_INTERVAL=2  # Run every 2 hours
```

### View the News Brief

The news brief is saved as Markdown in `news_brief.md` (or the path specified in your `.env` file). You can view this file in any Markdown viewer or converter.

## Configuration

Create a `.env` file with the following settings:

```
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=sqlite:///feeder.db
OUTPUT_FILE=news_brief.md
SCHEDULE_INTERVAL=1
```

## Usage

### Running the Pipeline

You can run the pipeline in different ways:

1. Run once and exit:
   ```
   python run.py --run
   ```

2. Run on a schedule (default is hourly):
   ```
   python run.py --schedule
   ```

3. Run on a schedule with custom interval:
   ```
   python run.py --schedule --interval 2
   ```

### Managing RSS Feeds

The application comes with a feed management tool:

1. List all feeds:
   ```
   python -m feeder.scripts.manage_feeds list
   ```

2. Add a new feed:
   ```
   python -m feeder.scripts.manage_feeds add "Feed Name" "https://example.com/feed.xml"
   ```

3. Remove a feed:
   ```
   python -m feeder.scripts.manage_feeds remove <feed_id>
   ```

4. Test a feed without adding it:
   ```
   python -m feeder.scripts.manage_feeds test "https://example.com/feed.xml"
   ```

5. Activate/deactivate a feed:
   ```
   python -m feeder.scripts.manage_feeds activate <feed_id>
   python -m feeder.scripts.manage_feeds deactivate <feed_id>
   ```

6. Update all feeds:
   ```
   python -m feeder.scripts.manage_feeds update
   ```

## Pipeline Process

The application follows these steps:

1. **Feed Fetching**: Retrieves articles from RSS feeds stored in the database
2. **Content Extraction**: Extracts full article content from URLs
3. **Analysis**: Uses OpenAI's API to analyze article content, generating:
   - Summaries
   - Sentiment scores
   - Topic identification
   - Key entity extraction
   - Text embeddings for clustering
4. **Clustering**: Groups similar articles using semantic similarity
5. **News Brief Generation**: Creates a markdown file with:
   - Timestamp and statistics
   - Key insights derived from analysis
   - Clustered articles with summaries

## Output

The pipeline generates a markdown file (`news_brief.md` by default) containing:
- Timestamp and summary statistics
- AI-generated key insights 
- Clustered articles organized by topic
- Article summaries and sources

## Automation

The pipeline can be scheduled to run at regular intervals (hourly by default). When run in scheduled mode, it will:

1. Execute the complete pipeline immediately
2. Schedule future runs at the specified interval
3. Continue running until interrupted (Ctrl+C)

## License

This project is licensed under the MIT License. 