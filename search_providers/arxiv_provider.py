from datetime import datetime
from typing import Dict, Any
import sys
from pathlib import Path
import requests
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

# Add parent directory to path for imports when running as script
if __name__ == "__main__":
    sys.path.append(str(Path(__file__).parent.parent))
    from search_providers.base_provider import BaseSearchProvider
else:
    from .base_provider import BaseSearchProvider

class  ArXivSearchProvider(BaseSearchProvider): 
    """
    arXiv search implementation of the search provider interface.
    Handles searches related to research articles from arXiv.
    Credit: code inspired by https://medium.com/@bargadyahmed/web-scraping-and-data-collection-from-arxiv-articles-3d3f3e2532ec
    """
    BASE_SEARCH_ENDPOINT = "http://export.arxiv.org/api"
    
    def __init__(self):
        """
        Initialize the arxiv search provider.
        """
        # search url
        self.ARXIV_SEARCH_URL = "https://export.arxiv.org/api/query?search_query=all:"
        # abs url
        self.ARXIV_ABS_URL = "https://arxiv.org/abs/"
        # Tracks the time of the last request
        self.last_request_time = 0  
        self.current_index = 0
    
    def is_configured(self) -> bool:
        """
        Check if the arXiv provider is properly configured.
        
        Returns:
            bool indicating if the arXiv provider is ready to use
        """
        abs_resp = requests.get(self.ARXIV_ABS_URL+"1507.00123")
        if abs_resp.status_code != 200:
            return False
        
        query = "how to reduce latency"
        encoded_query = quote(query)
        search_resp = requests.get(self.ARXIV_SEARCH_URL+encoded_query)
        if search_resp.status_code != 200:
            return False

        return True
    
    def parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Parse the XML response from the arXiv API.
        
        Args:
            response: The requests.Response object containing the API response
        
        Returns:
            Dict containing the parsed search results or error information
        """
        try:
            # Parse the XML response
            root = ET.fromstring(response.content)
            namespace = {"atom": "http://www.w3.org/2005/Atom"}
            
            results = []
            for entry in root.findall("atom:entry", namespace):
                # Extract information for each entry, with safeguards
                title = entry.find("atom:title", namespace)
                summary = entry.find("atom:summary", namespace)
                link = entry.find("atom:link[@rel='alternate']", namespace)
                authors = [
                    author.find("atom:name", namespace).text.strip()
                    for author in entry.findall("atom:author", namespace)
                ]
                published_date = entry.find("atom:published", namespace).text.strip()
                date_obj = datetime.strptime(published_date, '%Y-%m-%dT%H:%M:%SZ')
                published_date = date_obj.date()

                updated_date = entry.find("atom:updated", namespace).text.strip()
                date_obj = datetime.strptime(updated_date, '%Y-%m-%dT%H:%M:%SZ')
                updated_date = date_obj.date()

                # Add the extracted information to the results list
                results.append({
                    "title": title.text.strip() if title is not None else "No Title",
                    "summary": summary.text.strip() if summary is not None else "No Summary",
                    "link": link.attrib["href"] if link is not None else "No Link",
                    "authors": authors if authors else ["No Authors"],
                    "published_date": published_date.strftime('%Y-%m-%d') if published_date else "No Date",
                    "updated_date": updated_date.strftime('%Y-%m-%d') if updated_date else "No Date"
                })
            self.current_index += len(results)+1  # Update the current index for the next search
            return {"results": results}
        except ET.ParseError:
            return {"status": "error", "message": "Failed to parse XML response."}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Perform a search using the arXiv provider.
        
        Args:
            query: The search query string
            **kwargs: Additional search parameters specific to the provider
            
        Returns:
            Dict containing the search results or error information
        """
        # Check configuration of arXiv urls
        if not self.is_configured():
            return {'error': 'ArXiv urls not configured properly'}

        # Enforce the 3-second delay between requests for the arXiv provider Gentleman's Agreement
        current_time = time.time()
        if current_time - self.last_request_time < 3:
            time.sleep(3 - (current_time - self.last_request_time))
        
        # Encode the query to make it URL-safe
        encoded_query = quote(query)
        
        # Default parameters for the search query
        start = self.current_index  # Starting index for search results so that we dont repeat results
        max_results = kwargs.get("max_results", 10)  # Number of results to fetch
        
        # Construct the full URL
        url = f"{self.ARXIV_SEARCH_URL}{encoded_query}&start={start}&max_results={max_results}"
        
        try:
            # Perform the HTTP GET request
            response = requests.get(url, timeout=10)  # Added a timeout for network requests
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Update the last request time
            self.last_request_time = time.time()
            
            # Return the results
            return self.parse_response(response)
        
        except requests.RequestException as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

if __name__ == "__main__":
    # Example usage of the ArXivSearchProvider class
    provider = ArXivSearchProvider()
    if not provider.is_configured():
        print("Error: ArXiv urls not configured properly")
        exit(1)
    
    # Perform a search for articles
    print("\n=== Testing arXiv Search ===")
    
    print("Query: how do i reduce llm latency")
    results = provider.search("how do i reduce llm latency")
    
    if 'error' in results:
        print(f"Error in general search: {results['error']}")
    else:
        print("\n=== Testing Results Retrieval ===")
        print("Total Results:", len(results))
        for idx, result in enumerate(results["results"], 1):
            print("------------------------------")
            print(f"\n{idx}. Title: {result['title']}")
            print(f"Summary: {result['summary']}...")
            print(f"Authors: {', '.join(result['authors'])}")
            print(f"Link: {result['link']}")
            print("------------------------------")
        
        print("\n=== Normalized Results ===")
        normalized = {
            'success': True,
            'error': None,
            'provider': provider,
            'results': []
        }
        normalized['results'] = [{
                'title': r.get('title', ''),
                'url': r.get('link', ''),
                'content': r.get('summary', '')[:500],
                'score': float(r.get('score', 0.0)),
                'published_date': r.get('published_date')
            } for r in results.get('results', [])]
        
        for norm in normalized["results"]:  
            print("Normalized Result:", norm)
        
        print("\n=== End of Main ===")