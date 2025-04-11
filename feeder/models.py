from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///feeder.db")

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class Feed(Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    url = Column(String(2083), nullable=False, unique=True)
    last_fetched = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    articles = relationship("Article", back_populates="feed")

    def __repr__(self):
        return f"<Feed(name='{self.name}', url='{self.url}')>"


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("feeds.id"))
    title = Column(String(512), nullable=False)
    url = Column(String(2083), nullable=False, unique=True)
    published_at = Column(DateTime, nullable=True)
    author = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    content_extracted = Column(Boolean, default=False)
    analyzed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    feed = relationship("Feed", back_populates="articles")
    analysis = relationship("ArticleAnalysis", uselist=False, back_populates="article")
    cluster_membership = relationship("ClusterMembership", back_populates="article")

    def __repr__(self):
        return f"<Article(title='{self.title}', url='{self.url}')>"


class ArticleAnalysis(Base):
    __tablename__ = "article_analyses"

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), unique=True)
    sentiment_score = Column(Float, nullable=True)
    topics = Column(String(512), nullable=True)  # Comma-separated list of topics
    key_entities = Column(String(1024), nullable=True)  # JSON string of key entities
    summary = Column(Text, nullable=True)
    embedding = Column(Text, nullable=True)  # Stored as JSON string
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    article = relationship("Article", back_populates="analysis")

    def __repr__(self):
        return f"<ArticleAnalysis(article_id={self.article_id})>"


class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    run_id = Column(String(255), nullable=False)  # Identifies the clustering run
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    members = relationship("ClusterMembership", back_populates="cluster")

    def __repr__(self):
        return f"<Cluster(id={self.id}, name='{self.name}')>"


class ClusterMembership(Base):
    __tablename__ = "cluster_memberships"

    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id"))
    article_id = Column(Integer, ForeignKey("articles.id"))
    similarity_score = Column(Float)  # How similar this article is to the cluster center
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    cluster = relationship("Cluster", back_populates="members")
    article = relationship("Article", back_populates="cluster_membership")

    def __repr__(self):
        return f"<ClusterMembership(cluster_id={self.cluster_id}, article_id={self.article_id})>"


class NewsBrief(Base):
    __tablename__ = "news_briefs"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    article_count = Column(Integer, nullable=False)
    cluster_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<NewsBrief(id={self.id}, created_at='{self.created_at}')>"


def init_db():
    Base.metadata.create_all(engine) 