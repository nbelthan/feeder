import os
import logging
from typing import Dict, Any, List, Optional
import datetime
import json
import traceback
from collections import Counter
import google.generativeai as genai

from feeder.models import Session, NewsBrief, ArticleAnalysis
from feeder.clustering import get_clusters

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
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 2048,
}

def generate_news_brief(
    run_id: Optional[str] = None,
    output_file: Optional[str] = None,
    session: Optional[Session] = None
) -> str:
    """
    Generate a news brief from analyzed articles.
    
    Args:
        run_id: Unique identifier for this run
        output_file: Path to save the news brief (if None, uses env var OUTPUT_FILE)
        session: SQLAlchemy session. If None, a new session will be created.
        
    Returns:
        Path to the generated news brief markdown file.
    """
    close_session = False
    if session is None:
        session = Session()
        close_session = True
    
    # Use specified output file or default
    if not output_file:
        output_file = os.getenv("OUTPUT_FILE", "news_brief.md")
    
    try:
        # Get article clusters
        clusters = get_clusters(session)
        
        # Generate the news brief
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        
        # Create news brief heading
        brief_text = f"# Daily News Brief\n\n**{date_str}**\n\n"
        
        # Generate insights
        insights = generate_insights(clusters, session)
        if insights:
            brief_text += "## Key Insights\n\n"
            for insight in insights:
                brief_text += f"- {insight}\n"
            brief_text += "\n"
        
        # Add cluster summaries
        brief_text += "## Top Stories\n\n"
        
        for i, cluster in enumerate(clusters):
            # Get the most representative article for the cluster
            if not cluster["articles"]:
                continue
                
            # Sort articles by published date (newest first)
            sorted_articles = sorted(
                cluster["articles"], 
                key=lambda x: x.published_at if x.published_at else datetime.datetime.min, 
                reverse=True
            )
            
            # Get the most recent article
            main_article = sorted_articles[0]
            main_analysis = session.query(ArticleAnalysis).filter(
                ArticleAnalysis.article_id == main_article.id
            ).first()
            
            if not main_analysis:
                continue
            
            # Get summary
            summary = main_analysis.summary if hasattr(main_analysis, "summary") else ""
            
            # Collect sentiment scores
            sentiment_scores = []
            for article in cluster["articles"]:
                analysis = session.query(ArticleAnalysis).filter(
                    ArticleAnalysis.article_id == article.id
                ).first()
                if analysis and hasattr(analysis, "sentiment_score"):
                    try:
                        sentiment_scores.append(float(analysis.sentiment_score))
                    except (ValueError, TypeError):
                        pass
            
            # Calculate average sentiment
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
            
            # Describe sentiment
            sentiment_description = "neutral"
            if avg_sentiment > 0.3:
                sentiment_description = "positive"
            elif avg_sentiment < -0.3:
                sentiment_description = "negative"
            
            # Collect all topics
            all_topics = []
            for article in cluster["articles"]:
                analysis = session.query(ArticleAnalysis).filter(
                    ArticleAnalysis.article_id == article.id
                ).first()
                if analysis and hasattr(analysis, "topics"):
                    try:
                        topics = json.loads(analysis.topics)
                        all_topics.extend(topics)
                    except json.JSONDecodeError:
                        # Try comma-separated format
                        topics = analysis.topics.split(",")
                        all_topics.extend([t.strip() for t in topics if t.strip()])
                        
            # Get most common topics
            topic_counter = Counter(all_topics)
            top_topics = [topic for topic, count in topic_counter.most_common(3)]
            
            # Format as markdown
            brief_text += f"### {main_article.title}\n\n"
            brief_text += f"*{sentiment_description.capitalize()} sentiment • {', '.join(top_topics) if top_topics else 'No topics identified'}*\n\n"
            brief_text += f"{summary}\n\n"
            
            # Add source information
            sources = set(article.feed.name for article in cluster["articles"] if article.feed and article.feed.name)
            if sources:
                brief_text += f"*Sources: {', '.join(sources)}*\n\n"
                
            # Add a divider (except after the last cluster)
            if i < len(clusters) - 1:
                brief_text += "---\n\n"
        
        # Create a new news brief record
        news_brief = NewsBrief(
            filename=output_file,
            content=brief_text,
            article_count=sum(len(cluster["articles"]) for cluster in clusters),
            cluster_count=len(clusters)
        )
        session.add(news_brief)
        session.commit()
        
        # Write to file
        with open(output_file, "w") as f:
            f.write(brief_text)
        
        logger.info(f"News brief generated and saved to {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error generating news brief: {str(e)}")
        logger.error(traceback.format_exc())
        if close_session:
            session.rollback()
        raise
        
    finally:
        if close_session:
            session.close()

def generate_insights(clusters: List[Dict[str, Any]], session: Session) -> List[str]:
    """
    Generate key insights based on clustered articles.
    
    Args:
        clusters: List of cluster dictionaries
        session: SQLAlchemy session
        
    Returns:
        List of insight strings.
    """
    try:
        if not clusters:
            return []
            
        # Collect information about the clusters
        cluster_info = []
        
        for cluster in clusters:
            articles = cluster["articles"]
            if not articles:
                continue
                
            # Get sentiment statistics
            sentiment_scores = []
            for article in articles:
                analysis = session.query(ArticleAnalysis).filter(
                    ArticleAnalysis.article_id == article.id
                ).first()
                if analysis and hasattr(analysis, "sentiment_score"):
                    try:
                        sentiment_scores.append(float(analysis.sentiment_score))
                    except (ValueError, TypeError):
                        pass
            
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
            
            # Get topics
            all_topics = []
            for article in articles:
                analysis = session.query(ArticleAnalysis).filter(
                    ArticleAnalysis.article_id == article.id
                ).first()
                if analysis and hasattr(analysis, "topics"):
                    try:
                        topics = json.loads(analysis.topics)
                        all_topics.extend(topics)
                    except json.JSONDecodeError:
                        # Try comma-separated format
                        topics = analysis.topics.split(",")
                        all_topics.extend([t.strip() for t in topics if t.strip()])
            
            # Get most common topics
            topic_counter = Counter(all_topics)
            top_topics = [topic for topic, count in topic_counter.most_common(3)]
            
            # Get main article and its summary
            main_article = articles[0]
            main_analysis = session.query(ArticleAnalysis).filter(
                ArticleAnalysis.article_id == main_article.id
            ).first()
            
            summary = ""
            if main_analysis and hasattr(main_analysis, "summary"):
                summary = main_analysis.summary
                
            # Get sources
            sources = list(set(article.feed.name for article in articles if article.feed and article.feed.name))
            
            # Add to cluster info
            cluster_info.append({
                "title": main_article.title,
                "summary": summary,
                "sentiment": avg_sentiment,
                "topics": top_topics,
                "sources": sources,
                "article_count": len(articles)
            })
            
        # Determine overall sentiment tone
        all_sentiments = [c["sentiment"] for c in cluster_info if "sentiment" in c]
        avg_overall_sentiment = sum(all_sentiments) / len(all_sentiments) if all_sentiments else 0
        
        sentiment_description = "neutral"
        if avg_overall_sentiment > 0.3:
            sentiment_description = "positive"
        elif avg_overall_sentiment < -0.3:
            sentiment_description = "negative"
        
        # Generate insights using Google Gemini
        logger.info("Preparing to generate insights with Google Gemini")
        
        prompt = f"""
        I have analyzed news articles and found the following patterns:
        
        Overall sentiment: {sentiment_description}
        
        Top clusters:
        {json.dumps(cluster_info, indent=2)}
        
        Based on this data, please generate 3-5 key insights about today's news. Each insight should be a single sentence that captures an important trend, pattern, or observation across the articles. Focus on identifying:
        
        1. Major themes or narratives
        2. Significant shifts or developments
        3. Geographic or demographic patterns
        4. Contrasting perspectives
        5. Underlying issues or causes
        
        Format each insight as a single, concise sentence. Do not include bullet points, numbers, or any other formatting.
        """
        
        try:
            logger.info("Calling Google Gemini API for insights generation")
            model = genai.GenerativeModel(
                model_name="gemini-1.5-pro",
                generation_config=generation_config
            )
            response = model.generate_content(prompt)
            logger.info("Google Gemini API call for insights generation successful")
            
            insights_text = response.text
            
            # Process the insights: split by lines and clean up
            insights = []
            for line in insights_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Remove bullet points, numbers and other markers at the beginning
                if line.startswith(('- ', '• ', '* ', '1. ', '2. ', '3. ', '4. ', '5. ')):
                    line = line[2:].strip()
                    
                # Add if it's not empty
                if line:
                    insights.append(line)
            
            if not insights:
                # Fallback if processing didn't work
                insights = insights_text.split('.')
                insights = [i.strip() + '.' for i in insights if len(i.strip()) > 20]
                
            # Limit to 5 insights
            return insights[:5]
            
        except Exception as e:
            logger.error(f"Error generating insights with Google Gemini: {str(e)}")
            # Generate some basic insights as fallback
            insights = [
                "Today's news coverage shows a mix of domestic and international stories.",
                f"The overall tone of today's coverage is {sentiment_description}.",
                "Multiple sources are covering the same major events, indicating widespread interest."
            ]
            return insights
            
    except Exception as e:
        logger.error(f"Error in generate_insights: {str(e)}")
        return [] 