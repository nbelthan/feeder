import json
import uuid
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sklearn.cluster import DBSCAN
from sqlalchemy import and_
import datetime
from sklearn.metrics.pairwise import cosine_similarity

from feeder.models import Session, Article, ArticleAnalysis, Cluster, ClusterMembership

logger = logging.getLogger(__name__)


def get_article_embeddings(articles: List[Article]) -> Tuple[List[np.ndarray], List[int]]:
    """
    Extract embeddings from a list of analyzed articles.
    
    Args:
        articles: List of articles with analysis data
        
    Returns:
        Tuple of (embeddings as numpy arrays, article IDs)
    """
    embeddings = []
    article_ids = []
    
    for article in articles:
        if article.analysis and article.analysis.embedding:
            try:
                # Parse the embedding from JSON string
                embedding = json.loads(article.analysis.embedding)
                if embedding and len(embedding) > 0:
                    embeddings.append(np.array(embedding))
                    article_ids.append(article.id)
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Error parsing embedding for article {article.id}: {str(e)}")
    
    return embeddings, article_ids


def cluster_articles(
    min_articles: int = 10, 
    eps: float = 0.2, 
    min_samples: int = 3,
    session: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Cluster articles based on their embeddings.
    
    Args:
        min_articles: Minimum number of articles needed for clustering
        eps: DBSCAN epsilon parameter (maximum distance between samples)
        min_samples: DBSCAN min_samples parameter
        session: SQLAlchemy session. If None, a new session will be created.
        
    Returns:
        Dictionary with cluster stats.
    """
    close_session = False
    if session is None:
        session = Session()
        close_session = True
    
    try:
        # Get analyzed articles
        articles = session.query(Article).filter(
            Article.analyzed == True
        ).join(Article.analysis).all()
        
        logger.info(f"Got {len(articles)} analyzed articles for clustering")
        
        if len(articles) < min_articles:
            logger.warning(f"Not enough articles for clustering. Need at least {min_articles}.")
            return {
                "status": "insufficient_data",
                "article_count": len(articles),
                "cluster_count": 0
            }
        
        # Get embeddings
        embeddings, article_ids = get_article_embeddings(articles)
        
        if len(embeddings) < min_articles:
            logger.warning(f"Not enough valid embeddings for clustering. Got {len(embeddings)}, need {min_articles}.")
            return {
                "status": "insufficient_embeddings",
                "article_count": len(articles),
                "valid_embeddings": len(embeddings),
                "cluster_count": 0
            }
        
        # Convert to numpy array for clustering
        X = np.array(embeddings)
        
        # Perform clustering
        clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(X)
        labels = clustering.labels_
        
        # Count clusters (excluding noise marked as -1)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        
        logger.info(f"Clustering complete. Found {n_clusters} clusters.")
        
        # Generate a unique ID for this clustering run
        run_id = str(uuid.uuid4())
        
        # Create clusters in database
        cluster_map = {}  # Map of label -> Cluster object
        
        for label in set(labels):
            if label == -1:
                # Skip noise points
                continue
                
            # Create cluster
            cluster = Cluster(
                name=f"Cluster {label}",
                description="",
                run_id=run_id
            )
            session.add(cluster)
            session.flush()  # Get the ID
            cluster_map[label] = cluster
        
        # Create cluster memberships
        for i, label in enumerate(labels):
            if label == -1:
                # Skip noise points
                continue
                
            article_id = article_ids[i]
            cluster = cluster_map[label]
            
            # Calculate similarity score (can be enhanced in future)
            similarity_score = 1.0  # Placeholder
            
            # Create membership
            membership = ClusterMembership(
                cluster_id=cluster.id,
                article_id=article_id,
                similarity_score=similarity_score
            )
            session.add(membership)
        
        # Generate names for clusters based on common topics
        name_clusters(cluster_map, session)
        
        # Commit all changes
        session.commit()
        
        return {
            "status": "success",
            "run_id": run_id,
            "article_count": len(articles),
            "valid_embeddings": len(embeddings),
            "cluster_count": n_clusters,
            "noise_count": list(labels).count(-1)
        }
        
    except Exception as e:
        logger.error(f"Error during clustering: {str(e)}")
        session.rollback()
        return {
            "status": "error",
            "error": str(e)
        }
        
    finally:
        if close_session:
            session.close()


def name_clusters(cluster_map: Dict[int, Cluster], session: Session) -> None:
    """
    Generate descriptive names for clusters based on article topics.
    
    Args:
        cluster_map: Dictionary mapping cluster labels to Cluster objects
        session: SQLAlchemy session
    """
    for label, cluster in cluster_map.items():
        # Get all articles in this cluster
        memberships = session.query(ClusterMembership).filter(
            ClusterMembership.cluster_id == cluster.id
        ).all()
        
        # Extract article IDs
        article_ids = [m.article_id for m in memberships]
        
        # Get the analyses for these articles
        analyses = session.query(ArticleAnalysis).filter(
            ArticleAnalysis.article_id.in_(article_ids)
        ).all()
        
        # Collect all topics
        all_topics = []
        for analysis in analyses:
            if analysis.topics:
                topics = analysis.topics.split(",")
                all_topics.extend([t.strip() for t in topics])
        
        # Count occurrences
        topic_counts = {}
        for topic in all_topics:
            if topic:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        # Sort by frequency
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_topics:
            # Take the most common topics
            top_topics = [t for t, _ in sorted_topics[:3]]
            cluster.name = " / ".join(top_topics)
            
            # Generate a description
            if len(memberships) == 1:
                cluster.description = f"Single article on {top_topics[0]}"
            else:
                cluster.description = f"Group of {len(memberships)} articles about {', '.join(top_topics)}"
        else:
            # Fallback if no topics found
            cluster.name = f"Cluster {label}"
            cluster.description = f"Group of {len(memberships)} articles"


def get_clusters(session: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    Get article clusters based on their embeddings.
    
    Args:
        session: SQLAlchemy session. If None, a new session will be created.
        
    Returns:
        List of clusters, each containing metadata and articles.
    """
    close_session = False
    if session is None:
        session = Session()
        close_session = True
    
    try:
        # Get all analyzed articles with embeddings
        analyses = session.query(ArticleAnalysis).all()
        if not analyses:
            logger.warning("No analyzed articles found for clustering")
            return []
        
        # Get article data and validated embeddings
        articles_data = []
        valid_embeddings = []
        expected_dim = None # Track expected embedding dimension
        
        for analysis in analyses:
            # Load the article
            article = session.query(Article).filter(Article.id == analysis.article_id).first()
            if not article:
                logger.warning(f"Article not found for analysis ID {analysis.id}, skipping.")
                continue
            
            if not analysis.embedding:
                logger.warning(f"Article {article.id} ({article.title}) has no embedding, skipping.")
                continue

            # Get and validate embedding
            try:
                embedding = json.loads(analysis.embedding)
                
                # Basic validation
                if not embedding or not isinstance(embedding, list):
                    logger.warning(f"Invalid embedding format for article {article.id} (not a list or empty), skipping.")
                    continue
                    
                # Check dimension consistency
                current_dim = len(embedding)
                if expected_dim is None:
                    expected_dim = current_dim # Set expected dimension from first valid embedding
                    logger.info(f"Setting expected embedding dimension to {expected_dim}")
                elif current_dim != expected_dim:
                    logger.warning(f"Article {article.id} has inconsistent embedding dimension ({current_dim} vs expected {expected_dim}), skipping.")
                    continue

                # If valid and consistent, add it
                valid_embeddings.append(embedding)
                articles_data.append(article) # Keep track of the corresponding article

            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Error loading/parsing embedding for article {analysis.article_id}: {str(e)}, skipping.")
        
        if not valid_embeddings:
            logger.warning("No valid & consistent embeddings found for clustering after validation")
            return []
            
        logger.info(f"Proceeding to cluster with {len(valid_embeddings)} valid embeddings (dimension: {expected_dim})")
        
        # Convert validated embeddings to numpy array
        # This should now be safe
        embeddings_array = np.array(valid_embeddings, dtype=float)
        
        # Compute similarity matrix
        similarity_matrix = cosine_similarity(embeddings_array)
        
        # Convert to distance matrix (1 - similarity)
        distance_matrix = 1 - similarity_matrix

        # Clip negative values due to floating point inaccuracies
        distance_matrix = np.maximum(0, distance_matrix)
        
        # Cluster with DBSCAN
        clustering = DBSCAN(
            eps=0.3,  # Max distance between samples
            min_samples=1,  # Min samples to form a dense region
            metric='precomputed'
        ).fit(distance_matrix)
        
        # Get cluster labels
        labels = clustering.labels_
        
        # Ensure we have at least one valid cluster
        if max(labels) < 0:  # All points are noise
            # Fallback to one cluster
            labels = [0] * len(embeddings_array)
        
        # Create cluster objects
        result_clusters = []
        
        # Process each cluster
        for cluster_id in sorted(set(labels)):
            # Skip noise cluster (-1)
            if cluster_id == -1:
                continue
                
            # Get articles in this cluster
            cluster_indices = [i for i, c in enumerate(labels) if c == cluster_id]
            cluster_articles = [articles_data[i] for i in cluster_indices]
            
            # Create cluster object
            cluster = {
                "id": cluster_id,
                "articles": cluster_articles
            }
            
            result_clusters.append(cluster)
            
        logger.info(f"Clustering complete. Found {len(result_clusters)} clusters.")
        return result_clusters
        
    finally:
        if close_session:
            session.close()


def cluster_embeddings(embeddings: np.ndarray) -> List[int]:
    """
    Cluster embeddings using DBSCAN.
    
    Args:
        embeddings: Array of embedding vectors
        
    Returns:
        List of cluster IDs for each embedding
    """
    # Handle small number of articles
    if len(embeddings) < 3:
        return [0] * len(embeddings)  # Put everything in one cluster
    
    # Compute similarity matrix
    similarity_matrix = cosine_similarity(embeddings)
    
    # Convert to distance matrix (1 - similarity)
    distance_matrix = 1 - similarity_matrix

    # Clip negative values due to floating point inaccuracies
    distance_matrix = np.maximum(0, distance_matrix)
    
    # Cluster with DBSCAN
    clustering = DBSCAN(
        eps=0.3,  # Max distance between samples
        min_samples=1,  # Min samples to form a dense region
        metric='precomputed'
    ).fit(distance_matrix)
    
    # Get cluster labels
    labels = clustering.labels_
    
    # Ensure we have at least one valid cluster
    if max(labels) < 0:  # All points are noise
        # Fallback to one cluster
        return [0] * len(embeddings)
    
    return labels.tolist() 