import mwclient
import yaml
import os
import json
import logging
from dotenv import load_dotenv
from src.generators.lua_module_generator import to_lua_table


class WikiUploader:
    """
    Handles versioning, formatting, and uploading data to a MediaWiki site.
    """
    def __init__(self, config_path='upload_config.yaml'):
        load_dotenv()
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.upload_config = yaml.safe_load(f)
        except FileNotFoundError:
            logging.error(f"{config_path} not found.")
            self.upload_config = {}
        
        self.prefix = self.upload_config.get('prefix', '')
        self.history_prefix = self.upload_config.get('history_prefix', '/History')
        wiki_config = self.upload_config.get('wiki', {})
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
    
    def _upload_content(self, page_name, content, summary, is_history=False):
        """
        Helper function to upload content to a single wiki page.
        """
        
        if not self.site:
            logging.warning(f"SKIPPING upload to '{page_name}' (no wiki connection)")
            return
        full_page_name = page_name if is_history else self.prefix + page_name
        logging.info(f"Uploading to '{full_page_name}'...")
        try:
            page = self.site.pages[full_page_name]
            page.save(content, summary=summary)
            logging.info(f"Successfully uploaded to {full_page_name}")
        except Exception as e:
            logging.error(f"Failed to upload to {full_page_name}: {e}")
    
    def _upload_modules(self, version, spec_name=None):
        logging.info("--- Uploading Lua modules... ---")
        module_map = self.upload_config.get('modules', {})
        
        if not module_map:
            logging.warning("No module mappings found in upload_config.yaml")
            return
        upload_map = module_map
        
        if spec_name:
            logging.info(f"Filtering module upload for spec: {spec_name}")
            base_spec_name = spec_name.replace('_spec', '')
            upload_map = {
                k: v for k, v in module_map.items()
                if k.startswith(base_spec_name) or k == 'utils.lua'
            }
        staging_dir = "staging/modules"
        summary = f"Automated module update for version {version}"
        
        for local_file, wiki_page_name in upload_map.items():
            local_path = os.path.join(staging_dir, local_file)
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._upload_content(wiki_page_name, content, summary)
            except FileNotFoundError:
                logging.error(f"Local file not found: {local_path}")
            except Exception as e:
                logging.error(f"Error while processing {local_path}: {e}")
    
    def _upload_meta(self, version):
        logging.info("--- Updating metadata file... ---")
        version_id = version
        meta_page_name = self.upload_config.get('meta_page', '/meta.json')
        logging.info(f"Updating metadata file: {self.prefix}{meta_page_name}")
        meta_data = {"versions": [], "codex_added_fields": []}
        try:
            with open('src/generators/templates/meta.json', 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
        except FileNotFoundError:
            logging.warning("meta.json not found, creating a new one.")
        
        if version_id not in meta_data['versions']:
            meta_data['versions'].insert(0, version_id)
        self._upload_content(meta_page_name, json.dumps(meta_data, separators=(',', ':')), f"Add data version {version_id}")
    
    def _upload_data(self, version, spec_name=None):
        logging.info("--- Uploading data files... ---")
        data_map = self.upload_config.get('data', {})
        
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
        
        for local_file, wiki_page_name in upload_map.items():
            local_path = os.path.join("staging/output", local_file)
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
                self._upload_content(wiki_page_name, content_to_upload, summary)
                history_page_name = f"{self.prefix}{self.history_prefix}/{version_id}{wiki_page_name}"
                self._upload_content(history_page_name, content_to_upload, summary, is_history=True)
            except FileNotFoundError:
                logging.error(f"Local file not found: {local_path}")
            except Exception as e:
                logging.error(f"Error while processing {local_path}: {e}")
    
    def upload(self, upload_target, version, spec_name=None):
        if not version:
            logging.error("Upload action requires a version string. Use the --version argument.")
            return
        
        if upload_target in ['modules', 'data', 'all']:
            self._upload_meta(version)
        
        if upload_target in ['modules', 'all']:
            self._upload_modules(version, spec_name=spec_name)
        
        if upload_target in ['data', 'all']:
            self._upload_data(version, spec_name=spec_name)
