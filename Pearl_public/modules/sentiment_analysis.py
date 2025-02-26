import asyncio
import logging
from datetime import datetime, timedelta
from textblob import TextBlob
from modules.internet_search import DuckDuckGoSearchCrawler
from core.ollama_integration import ask_ollama

logging.basicConfig(level=logging.INFO)

class SentimentAnalysis:
    def __init__(self, num_results=10):
        """Initialize the sentiment analysis module with web search capability."""
        self.searcher = DuckDuckGoSearchCrawler(num_results)
        self.cutoff_date = datetime.utcnow() - timedelta(days=2)  # Only recent data (past 2 days)

    def analyze_sentiment(self, texts):
        """Perform sentiment analysis on a list of texts."""
        if not texts:
            return {"polarity": 0, "subjectivity": 0}

        total_polarity = 0
        total_subjectivity = 0
        for text in texts:
            sentiment = TextBlob(text).sentiment
            total_polarity += sentiment.polarity
            total_subjectivity += sentiment.subjectivity

        return {
            "polarity": total_polarity / len(texts),
            "subjectivity": total_subjectivity / len(texts),
        }

    async def perform_sentiment_analysis(self, topic):
        """Search for a topic, analyze sentiment, and summarize findings."""
        logging.info(f"Performing sentiment analysis for: {topic}")

        # Step 1: Fetch relevant articles using DuckDuckGo
        search_results = await self.searcher.search_and_crawl(topic)
        crawled_contents = [item["content"] for item in search_results["crawled_content"] if item["content"]]

        if not crawled_contents:
            return "No recent content available."

        # Step 2: Analyze sentiment of extracted content
        sentiment_scores = self.analyze_sentiment(crawled_contents)

        # Step 3: Summarize findings using Ollama AI
        summary_prompt = (
            f"Summarize the sentiment analysis of recent online discussions about '{topic}'.\n\n"
            f"The overall sentiment polarity is {sentiment_scores['polarity']:.2f}, and subjectivity is {sentiment_scores['subjectivity']:.2f}.\n"
            f"Provide a concise summary of the general opinion and trends from the articles."
        )
        summary = await ask_ollama(summary_prompt)

        return {
            "summary": summary,
            "sentiment_scores": sentiment_scores,
            "articles": [item["url"] for item in search_results["search_results"]],
        }

# Example Usage
if __name__ == "__main__":
    sa = SentimentAnalysis()
    topic = "NVIDIA stock movement"
    result = asyncio.run(sa.perform_sentiment_analysis(topic))
    print(result["summary"])
    print("\nRecent Articles:", result["articles"])