import os
import json
import logging
import requests
import zipfile

class CdnExtractor:
    """
    Extracts avatar data from a web URL or local file based on configuration.
    Supports remote fetching in live runs and local retrieval in historical runs.
    """
    _cache = {}

    def extract(self, source_info, config):
        path = source_info.get('path')
        sub_key = source_info.get('sub_key')
        if not path:
            logging.error(f"Source '{source_info.get('name')}' missing 'path'.")
            return None
            
        is_historical = config.get('is_historical', False)
        source_type = source_info.get('type')
        local_base = config.get('local_data_paths', {}).get(source_type, f"data/{source_type}")
        
        # Determine local path (add .json if missing)
        local_rel_path = f"{path}.json" if not path.endswith('.json') else path
        full_local_path = os.path.join(local_base, local_rel_path)
        
        # 1. Historical Mode or No URL config: Read from local/archive
        if is_historical:
            logging.info(f"Historical mode: Reading CDN data from local source: {full_local_path}")
            data = self._read_local(full_local_path)
            return data.get(sub_key, data) if sub_key and isinstance(data, dict) else data
            
        # 2. Live Mode: Fetch from URL (with caching)
        url = source_info.get('url')
        if not url:
            base_url = config.get('avatar_url')
            if not base_url:
                logging.error("No 'avatar_url' configured in codex_config.yaml and no explicit 'url' in source.")
                return None
            url = f"{base_url.rstrip('/')}/{path}"
            
        if url in self._cache:
            data = self._cache[url]
        else:
            logging.info(f"Fetching CDN data from: {url}")
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                self._cache[url] = data
                # Save for posterity/archival
                self._save_local(full_local_path, data)
            except Exception as e:
                logging.error(f"Failed to fetch CDN data from {url}: {e}")
                logging.info(f"Attempting fallback to local file: {full_local_path}")
                data = self._read_local(full_local_path)
        
        if sub_key and isinstance(data, dict):
            return data.get(sub_key, [])
        return data

    def _read_local(self, path):
        try:
            if ".zip/" in path:
                zip_path, member_path = path.split(".zip/", 1)
                zip_path += ".zip"
                with zipfile.ZipFile(zip_path, 'r') as z:
                    content = z.read(member_path)
                    return json.loads(content)
            else:
                if not os.path.exists(path):
                    logging.error(f"Local file not found: {path}")
                    return None
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Error reading local CDN file {path}: {e}")
            return None

    def _save_local(self, path, data):
        try:
            # Skip saving if it's a ZIP path (shouldn't happen in live mode)
            if ".zip/" in path:
                return
                
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logging.debug(f"Saved CDN data to {path}")
        except Exception as e:
            logging.warning(f"Failed to save local copy of CDN data: {e}")
