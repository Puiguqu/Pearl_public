import asyncio
import logging
import requests
from modules.internet_search import  DuckDuckGoSearchCrawler
from core.ollama_integration import ask_ollama
from modules.internet_search import DuckDuckGoSearchCrawler, search_news

logging.basicConfig(level=logging.INFO)


async def conduct_research(topic, chat_id=None):
    """
    Conducts research on a given topic by:
    1. Performing a Google search to gather recent sources.
    2. Extracting key summaries from those sources.
    3. Performing an in-depth analysis using AI.
    
    Args:
        topic (str): The research topic.
        chat_id (int, optional): Telegram chat ID to send results.
    
    Returns:
        str: A detailed research report.
    """
    logging.info(f"Starting research on: {topic}")
    
    # Step 1: Gather recent sources and summaries
    search_summary = await  search_news(query=topic)
    
    if not search_summary:
        return "No relevant sources found. Try refining your topic."
    
    logging.info("Research summary collected.")
    
    # Step 2: Generate an in-depth analysis
    prompt = (
        f"Research Topic: {topic}\n\n"
        f"Using the following summarized information from online sources:\n\n"
        f"{search_summary}\n\n"
        "Provide a comprehensive analysis of the topic, explaining key findings, trends, and recent developments."
        f"Ensure the analysis is at most 150 words."
    )
    
    detailed_analysis = await ask_ollama(prompt, chat_id=chat_id)
    
    # Final Report
    research_report = f"*In-Depth Analysis:**\n{detailed_analysis}"
    
    logging.info("Research completed successfully.")
    return research_report

# Example Usage
# asyncio.run(conduct_research("Quantum Computing"))
