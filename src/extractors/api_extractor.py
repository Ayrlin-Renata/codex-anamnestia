import requests
import logging
from .base_extractor import BaseExtractor


class ApiExtractor(BaseExtractor):
    """
    Extracts data from a remote API endpoint.
    """
    def extract(self, source_info):
        url = source_info['url']
        logging.info(f"Extracting data from API: {url}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.error(f"Error fetching data from {url}: {e}")
            return None
