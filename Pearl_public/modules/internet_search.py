import asyncio
import aiohttp
import logging
import pandas as pd
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from core.ollama_integration import ask_ollama  # Assumed to be asynchronous

# Set up logging
logging.basicConfig(level=logging.INFO)

class DuckDuckGoSearchCrawler:
    def __init__(self, num_results=10):
        """Initialize DuckDuckGo Search and Crawler."""
        self.num_results = num_results
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def duckduckgo_search(self, query):
        """Fetch search results from DuckDuckGo API."""
        logging.info(f"Searching DuckDuckGo for: {query}")
        results = []
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=self.num_results):
                results.append({
                    "title": result.get("title"),
                    "url": result.get("href"),
                    "snippet": result.get("body")
                })
        return results

    async def fetch_page_content(self, session, url):
        """Fetch webpage content asynchronously."""
        import random
        import time
        await asyncio.sleep(random.uniform(1,3))
        try:
            async with session.get(url, headers=self.headers, timeout=9) as response:
                if response.status != 200:
                    logging.warning(f"Skipping {url} (HTTP {response.status})")
                    return None
                return await response.text()
        except asyncio.TimeoutError:
            logging.warning(f"Timeout fetching {url}")
        except Exception as e:
            logging.warning(f"Failed to fetch {url}: {e}")
        return None

    async def extract_text_from_urls(self, urls):
        """Extract readable text content from a list of URLs."""
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_page_content(session, url) for url in urls]
            responses = await asyncio.gather(*tasks)

        extracted_data = []
        for url, html in zip(urls, responses):
            if html:
                soup = BeautifulSoup(html, "html.parser")
                text = self.extract_visible_text(soup)
                extracted_data.append({"url": url, "content": text})
            else:
                extracted_data.append({"url": url, "content": None})
        return extracted_data

    def extract_visible_text(self, soup):
        """Extract and clean text from a BeautifulSoup object."""
        for script in soup(["script", "style", "meta", "noscript"]):
            script.extract()
        return soup.get_text(separator="\n", strip=True)

    async def search_and_crawl(self, query):
        """Perform DuckDuckGo search and extract relevant content."""
        search_results = self.duckduckgo_search(query)
        urls = [result["url"] for result in search_results if result.get("url")]
        if not urls:
            logging.info("No URLs found in search. Skipping crawl.")
            return {"search_results": [], "crawled_content": []}

        crawled_content = await self.extract_text_from_urls(urls)

        return {
            "search_results": search_results,
            "crawled_content": crawled_content
        }

async def summarize_page_content(content):
    """
    Generate a summary for the provided page content using ask_ollama.
    The summarization prompt asks for a concise and relevant summary.
    """
    if not content or not content.strip():
        return "No content to summarize."
    prompt = f"Summarize the following text in a concise and relevant manner:\n\n{content}"
    try:
        summary = await ask_ollama(prompt)
    except Exception as e:
        logging.warning(f"Error summarizing content: {e}")
        summary = "Summary could not be generated."
    return summary

async def search_news(query: str):
    """
    Search the web for news and return refined summaries of the scraped pages.
    Each page's content is summarized for relevance.
    The output is formatted like an academic paper, with references at the bottom.
    """
    crawler = DuckDuckGoSearchCrawler(num_results=5)
    results = await crawler.search_and_crawl(query=query)
    crawled_contents = results.get("crawled_content", [])
    
    if not crawled_contents:
        return "No content available."

    summaries = []
    references = []
    ref_count = 1

    for item in crawled_contents:
        url = item.get("url")
        content = item.get("content")

        if content:
            summary = await summarize_page_content(content)
            summaries.append(f"[{ref_count}] {summary}")
            references.append(f"[{ref_count}] {url}")
            ref_count += 1

    if not summaries:
        return "No valid content available."

    final_summary = "\n\n".join(summaries)
    reference_section = "\n\nReferences:\n" + "\n".join(references)

    return f"{final_summary}{reference_section}"


async def main():
    """
    Perform a DuckDuckGo search and crawl for a default query ("latest news").
    Display the raw search results and extracted content for inspection.
    """
    crawler = DuckDuckGoSearchCrawler(num_results=5)
    results = await crawler.search_and_crawl(query="latest news")

    # Convert results to DataFrame for easy viewing
    df_results = pd.DataFrame(results["search_results"])
    df_crawled = pd.DataFrame(results["crawled_content"])

    print("\n🔍 Search Results:")
    print(df_results)

    print("\n📰 Extracted Content:")
    print(df_crawled)

    # Raise an error to indicate main() is not for production execution.
    raise RuntimeError("❌ `main()` is not meant to be executed.")

if __name__ == "__main__":
    asyncio.run(main())
