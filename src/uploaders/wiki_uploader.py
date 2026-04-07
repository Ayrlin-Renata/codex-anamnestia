import mwclient
import yaml
import os
import json
import logging
import time
from dotenv import load_dotenv
from src.generators.lua_module_generator import to_lua_table


class WikiUploader:
    """
    Handles versioning, formatting, and uploading data to a MediaWiki site.
    """
    def __init__(self, config_path='configs/upload_config.yaml'):
        load_dotenv()
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.upload_config = yaml.safe_load(f)
        except FileNotFoundError:
            logging.error(f"{config_path} not found.")
            self.upload_config = {}
        
        self.history_prefix = self.upload_config.get('history_prefix', '/History')
        self.shared_modules = self.upload_config.get('shared_modules', [])
        wiki_config = self.upload_config.get('wiki', {})
        self.upload_delay = wiki_config.get('upload_delay', 0)
        self.query_delay = wiki_config.get('query_delay', min(1.0, self.upload_delay / 2) if self.upload_delay > 0 else 0)
        host = wiki_config.get('host')
        path = wiki_config.get('path', '/w/')
        username = os.getenv("WIKI_USERNAME")
        password = os.getenv("WIKI_PASSWORD")
        
        if not all([host, username, password]):
            logging.error("Wiki host, username, or password not configured in upload_config.yaml or .env file.")
            logging.info("Skipping wiki connection.")
            self.site = None
            return
        logging.info(f"Connecting to wiki at {host}...")
        self.site = mwclient.Site(host, path=path)
        try:
            self.site.login(username, password)
            logging.info("Login successful.")
        except mwclient.errors.LoginError as e:
            logging.error(f"Login failed: {e}")
            self.site = None
    
    def _upload_content(self, page_name, prefix, content, summary, is_history=False):
        """
        Helper function to upload content to a single wiki page, skipping if identical to current content.
        Uses separate delays for queries vs uploads and handles 429 retries.
        """
        
        if not self.site:
            logging.warning(f"SKIPPING upload to '{page_name}' (no wiki connection)")
            return
        
        full_page_name = page_name if is_history else prefix + page_name
        
        # Check if upload is necessary by comparing with current page content
        is_already_up_to_date = False
        max_query_retries = 3
        for attempt in range(max_query_retries):
            try:
                if self.query_delay > 0:
                    time.sleep(self.query_delay)
                
                page = self.site.pages[full_page_name]
                if page.exists:
                    current_text = page.text()
                    
                    # Robust comparison: ignore leading/trailing whitespace
                    if current_text and current_text.strip() == content.strip():
                        logging.info(f"Page '{full_page_name}' is up to date. Skipping upload.")
                        is_already_up_to_date = True
                        break
                    
                    # Special handling for JSON comparison
                    if full_page_name.endswith('.json'):
                        try:
                            if json.loads(current_text) == json.loads(content):
                                logging.info(f"JSON data for '{full_page_name}' is identical. Skipping upload.")
                                is_already_up_to_date = True
                                break
                        except (json.JSONDecodeError, ValueError):
                            pass
                break # Page doesn't exist or is not up to date
            except Exception as e:
                # Handle 429 retries specifically
                if "429" in str(e) and attempt < max_query_retries - 1:
                    wait_time = (attempt + 1) * 5
                    logging.warning(f"429 Too Many Requests while querying {full_page_name}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logging.debug(f"Failed to fetch current content for {full_page_name}: {e}")
                    break
        
        if is_already_up_to_date:
            return
            
        # Perform the actual upload
        max_upload_retries = 3
        for attempt in range(max_upload_retries):
            try:
                if self.upload_delay > 0:
                    logging.debug(f"Rate limiting: Waiting {self.upload_delay}s before save...")
                    time.sleep(self.upload_delay)
                    
                logging.info(f"Uploading to '{full_page_name}'...")
                # Re-fetch page object if needed
                page = self.site.pages[full_page_name] if 'page' not in locals() else page
                page.save(content, summary=summary)
                logging.info(f"Successfully uploaded to {full_page_name}")
                break
            except Exception as e:
                if "429" in str(e) and attempt < max_upload_retries - 1:
                    wait_time = (attempt + 1) * 10 # Longer wait for save failures
                    logging.warning(f"429 Too Many Requests while uploading {full_page_name}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logging.error(f"Failed to upload to {full_page_name}: {e}")
                    break
    
    def _upload_modules(self, version, spec_name=None, target='all'):
        logging.info("--- Uploading Lua modules and/or Templates... ---")
        module_groups = self.upload_config.get('module_groups', [])
        
        if not module_groups:
            logging.warning("No module_groups found in upload_config.yaml")
            return
        staging_dir = "staging/modules"
        summary = f"Automated module update for version {version}"
        
        for group in module_groups:
            prefix = group.get('prefix', '')
            is_template = prefix.startswith('Template')
            
            if target == 'templates' and not is_template:
                continue
            if target == 'modules' and is_template:
                continue
                
            module_map = group.get('modules', {})
            current_staging_dir = group.get('staging_dir', staging_dir)
            upload_map = module_map
            
            if spec_name:
                logging.info(f"Filtering module upload for spec: {spec_name}")
                base_spec_name = spec_name.replace('_spec', '')
                is_map_spec = spec_name == 'map_location_spec'
                is_map_group = prefix == 'Map'
                
                if is_map_group and not is_map_spec:
                    continue
                elif not is_map_group and is_map_spec:
                    upload_map = {k: v for k, v in module_map.items() if k == 'utils.lua'}
                elif not is_map_group:
                    upload_map = {
                        k: v for k, v in module_map.items()
                        if k.startswith(base_spec_name) or k in self.shared_modules or 
                        (k.endswith('.wikitext') and (base_spec_name in k.lower() or k == 'Infobox.wikitext'))
                    }
                    if upload_map:
                        logging.info(f"Filtered {len(upload_map)} modules for upload (spec: {spec_name}): {list(upload_map.keys())}")
            
            for local_file, wiki_page_name in upload_map.items():
                local_path = os.path.join(current_staging_dir, local_file)
                try:
                    with open(local_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self._upload_content(wiki_page_name, prefix, content, summary)
                except FileNotFoundError:
                    logging.warning(f"Local file not found, skipping: {local_path}")
                except Exception as e:
                    logging.error(f"Error while processing {local_path}: {e}")
    
    def _upload_meta(self, version, is_historical=False):
        if is_historical:
            logging.info("--- Skipping metadata update for historical run ---")
            return
        logging.info("--- Updating metadata file... ---")
        version_id = version
        meta_page_name = self.upload_config.get('meta_page', '/meta.json')
        meta_prefix = "Module:Data"
        logging.info(f"Updating metadata file: {meta_prefix}{meta_page_name}")
        meta_data = {"versions": [], "codex_added_fields": []}
        try:
            with open('src/generators/templates/meta.json', 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
        except FileNotFoundError:
            logging.warning("meta.json not found, creating a new one.")
        
        if version_id not in meta_data['versions']:
            meta_data['versions'].insert(0, version_id)
        self._upload_content(meta_page_name, meta_prefix, json.dumps(meta_data, separators=(',', ':')), f"Add data version {version_id}")
    
    def _upload_data(self, version, spec_name=None, is_historical=False):
        import datetime
        logging.info("--- Uploading data files... ---")
        data_map = self.upload_config.get('data', {})
        data_prefix = "Module:Data"
        
        if not data_map:
            logging.warning("No data mappings found in upload_config.yaml")
            return
        upload_map = data_map
        
        if spec_name:
            logging.info(f"Filtering data upload for spec: {spec_name}")
            base_spec_name = spec_name.replace('_spec', '')
            upload_map = {
                k: v for k, v in data_map.items()
                if k.startswith(base_spec_name)
            }
        version_id = version
        logging.info(f"Using version ID for this run: {version_id}")
        
        for local_file, config in upload_map.items():
            wiki_page_name = config['page'] if isinstance(config, dict) else config
            history_type = config.get('history') if isinstance(config, dict) else None
            
            local_path = os.path.join("staging/outputs", local_file)
            logging.info(f"Processing data file: {local_path}")
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    resolved_data = json.load(f)
                summary = f"Automated data update for version {version_id}"
                content_to_upload = ''
                
                if wiki_page_name.endswith('.json'):
                    if isinstance(resolved_data, list):
                        content_to_upload = json.dumps({'data': resolved_data}, separators=(',', ':'))
                    else:
                        content_to_upload = json.dumps(resolved_data, separators=(',', ':'))
                else:
                    id_field = 'id'
                    data_for_lua = {item.get(id_field): item for item in resolved_data if item.get(id_field) is not None}
                    content_to_upload = "return " + to_lua_table(data_for_lua)
                
                if not is_historical:
                    self._upload_content(wiki_page_name, data_prefix, content_to_upload, summary)
                
                # History Handling
                if history_type == 'timestamped':
                    # Support for folders: /History/<version>/<page_basename>/<datetime>.json
                    page_basename = wiki_page_name.replace('.json', '').strip('/')
                    history_folder_title = f"{self.history_prefix}/{version_id}/{page_basename}".strip('/')
                    # Full page name for uploading includes prefix
                    history_folder_full = f"{data_prefix}/{history_folder_title}"
                    
                    logging.info(f"Checking for existing history in folder: {history_folder_full}")
                    latest_content = None
                    if self.site:
                        # Find all pages in this "folder" using the title part only (excluding "Module:")
                        # data_prefix is usually "Module:Data", so we take "Data/History/..."
                        search_prefix = f"Data/{history_folder_title}"
                        pages = list(self.site.allpages(prefix=search_prefix, namespace=828))
                        if pages:
                            # Sort by name descending to get the most recent timestamp
                            latest_page = sorted(pages, key=lambda p: p.name, reverse=True)[0]
                            logging.info(f"Comparing with latest history file: {latest_page.name}")
                            latest_content = latest_page.text()
                            
                            # Robust comparison: strip whitespace and try JSON parsing
                            if latest_content:
                                latest_content = latest_content.strip()
                                content_to_compare = content_to_upload.strip()
                                
                                if latest_content == content_to_compare:
                                    latest_content = content_to_upload # Equal strings
                                elif wiki_page_name.endswith('.json'):
                                    try:
                                        if json.loads(latest_content) == json.loads(content_to_compare):
                                            latest_content = content_to_upload # Equal objects
                                    except (json.JSONDecodeError, ValueError):
                                        pass
                    
                    if latest_content == content_to_upload:
                        logging.info(f"Content for '{page_basename}' is identical to the latest history file. Skipping history upload.")
                    else:
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
                        history_page_name = f"{history_folder_full}/{timestamp}.json"
                        self._upload_content(history_page_name, "", content_to_upload, summary, is_history=True)
                else:
                    # Legacy single history file
                    history_page_name = f"{data_prefix}{self.history_prefix}/{version_id}{wiki_page_name}"
                    self._upload_content(history_page_name, data_prefix, content_to_upload, summary, is_history=True)
                    
            except FileNotFoundError:
                logging.error(f"Local file not found: {local_path}")
            except Exception as e:
                logging.error(f"Error while processing {local_path}: {e}")
    
    def _upload_maps(self, version, spec_name=None):
        logging.info("--- Uploading JSON maps... ---")
        map_config = self.upload_config.get('maps', [])
        
        if not map_config:
            logging.warning("No map mappings found in upload_config.yaml")
            return
        staging_dir = "staging/maps"
        summary = f"Automated map update for version {version}"
        
        for map_item in map_config:
            local_file = map_item.get('file')
            wiki_page_name = map_item.get('page')
            
            if not local_file or not wiki_page_name:
                logging.warning(f"Skipping invalid map item: {map_item}")
                continue
            local_path = os.path.join(staging_dir, local_file)
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._upload_content(wiki_page_name, "", content, summary)
            except FileNotFoundError:
                logging.warning(f"Local file not found, skipping: {local_path}")
            except Exception as e:
                logging.error(f"Error while processing {local_path}: {e}")
    
    def _compare_versions(self, v1, v2):
        """
        Compares two version strings. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal.
        Handles dot-separated versions (e.g., 1.4.0.2).
        """
        if not v1 or not v2: return 0
        try:
            p1 = [int(p) for p in v1.split('.')]
            p2 = [int(p) for p in v2.split('.')]
            for i in range(max(len(p1), len(p2))):
                i1 = p1[i] if i < len(p1) else 0
                i2 = p2[i] if i < len(p2) else 0
                if i1 > i2: return 1
                if i1 < i2: return -1
            return 0
        except (ValueError, AttributeError):
            # Fallback to standard string comparison if not purely dots and numbers
            if v1 > v2: return 1
            if v1 < v2: return -1
            return 0

    def upload(self, upload_target, version, spec_name=None, is_historical=False, force_upload=False):
        if not version:
            logging.error("Upload action requires a version string. Use the --version argument.")
            return
        
        # --- Safety Check: Only upload if version is NEWER than online version ---
        if not is_historical and self.site:
            meta_page_name = self.upload_config.get('meta_page', '/meta.json')
            meta_prefix = "Module:Data"
            full_meta_name = f"{meta_prefix}{meta_page_name}"
            
            try:
                page = self.site.pages[full_meta_name]
                if page.exists:
                    meta_content = json.loads(page.text())
                    online_versions = meta_content.get('versions', [])
                    if online_versions:
                        latest_online = online_versions[0]
                        comparison = self._compare_versions(version, latest_online)
                        
                        if comparison <= 0:
                            if force_upload:
                                logging.warning(f"Version '{version}' is NOT newer than online version '{latest_online}', but forcing upload as requested.")
                            else:
                                logging.warning(f"ABORTING UPLOAD: Version '{version}' is not newer than the current online version '{latest_online}'.")
                                logging.info("Use --force-upload to bypass this safety check.")
                                return
                        else:
                            logging.info(f"Version check passed: '{version}' is newer than '{latest_online}'.")
            except Exception as e:
                logging.debug(f"Failed to fetch online metadata for safety check: {e}")
                # Continue if we can't check (e.g., first time setup)

        if upload_target in ['modules', 'data', 'maps', 'templates', 'all']:
            self._upload_meta(version, is_historical=is_historical)
        
        if upload_target in ['modules', 'templates', 'all']:
            self._upload_modules(version, spec_name=spec_name, target=upload_target)
        
        if upload_target in ['data', 'all']:
            self._upload_data(version, spec_name=spec_name, is_historical=is_historical)
        
        if upload_target in ['maps', 'all']:
            self._upload_maps(version, spec_name=spec_name)
