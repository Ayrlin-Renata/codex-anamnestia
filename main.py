import argparse
import os
import importlib
import yaml
import json
import logging

from src.utils.config_loader import load_spec
from src.transformers.standardizer import standardize_source
from src.resolver import resolve_data
from src.generators.lua_module_generator import generate_lua_modules
from src.generators.json_map_generator import generate_json_maps
from src.uploaders.wiki_uploader import WikiUploader
from src.utils.archiver import archive_version_sources

def get_extractor(type_name):
    if type_name == 'local_file':
        module_name = 'src.extractors.local_file_extractor'
        class_name = 'LocalFileExtractor'
    else:
        module_name = f"src.extractors.{type_name}_extractor"
        class_name = f"{type_name.capitalize()}Extractor"
    
    try:
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        logging.error(f"Could not load extractor {class_name} from {module_name}: {e}")
        raise

def run_processing_pipeline(spec_name, action, global_config):
    logging.info(f"--- Running processing for '{spec_name}' ---")
    
    spec = load_spec(spec_name)
    if not spec:
        logging.error(f"Specification '{spec_name}' not found or is empty.")
        return

    # --- Stage 1: Extraction & Standardization ---
    all_data = {}
    resolved_objects = []

    if action in ['collect', 'resolve', 'generate-modules', 'full']:
        logging.info("--- Stage 1: Starting Data Extraction & Standardization ---")
        for source_spec in spec.get('sources', []):
            source_name = source_spec['name']
            source_type = source_spec['type']
            
            if source_type == 'manual':
                raw_data = source_spec['data']
            else:
                try:
                    ExtractorClass = get_extractor(source_type)
                    extractor = ExtractorClass()
                    if source_type == 'local_file':
                        raw_data = extractor.extract(source_spec, global_config.get('local_data_paths', {}))
                    else:
                        raw_data = extractor.extract(source_spec)
                except Exception as e:
                    logging.error(f"Failed to run extractor for type '{source_type}'. {e}")
                    continue

            all_data[source_name] = standardize_source(raw_data, source_spec)
        logging.info("--- Stage 1: Finished ---")
        if action == 'collect': return

    # --- Stage 2: Resolution ---
    if action in ['resolve', 'generate-modules', 'full']:
        logging.info("--- Stage 2: Starting Data Resolution ---")
        resolution_strategy = spec.get('resolution_strategy', 'primary_source')
        if resolution_strategy == 'union':
            master_id_set = set()
            for union_source in spec.get('union_sources', []):
                source_name = union_source['name']
                id_field = union_source['id_field']
                source_data = all_data.get(source_name, {})
                for item_or_list in source_data.values():
                    if isinstance(item_or_list, list):
                        for sub_item in item_or_list:
                            item_id = sub_item.get(id_field)
                            if item_id is not None: master_id_set.add(item_id)
                    else:
                        item_id = item_or_list.get(id_field)
                        if item_id is not None: master_id_set.add(item_id)
            logging.info(f"Found {len(master_id_set)} unique IDs for union.")
            resolved_objects = resolve_data(spec, all_data, master_id_set)
        else:
            primary_source_name = spec.get('primary_source')
            primary_data = all_data.get(primary_source_name, {})
            # Flatten if primary source is group_by, though usually it's lookup
            items_to_process = []
            for item_or_list in primary_data.values():
                if isinstance(item_or_list, list):
                    items_to_process.extend(item_or_list)
                else:
                    items_to_process.append(item_or_list)
            resolved_objects = resolve_data(spec, all_data, items_to_process)
        logging.info("--- Stage 2: Finished ---")

        if resolved_objects:
            output_dir = "staging/output"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{spec_name}_resolved.json")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(resolved_objects, f, indent=2, ensure_ascii=False)
            logging.info(f"Saved final resolved data to {output_path}")
        if action == 'resolve': return

    # --- Stage 3: Module Generation ---
    if action in ['generate-modules', 'full']:
        logging.info("--- Stage 3: Starting Module Generation ---")
        if not resolved_objects:
            resolved_path = f"staging/output/{spec_name}_resolved.json"
            try:
                with open(resolved_path, 'r', encoding='utf-8') as f: resolved_objects = json.load(f)
                logging.info(f"Loaded resolved data from {resolved_path}")
            except FileNotFoundError:
                logging.error(f"Could not find {resolved_path}. Please run with '--action resolve' first.")
                return
        generate_lua_modules(spec_name, resolved_objects, global_config)
        generate_json_maps(spec_name, resolved_objects, global_config)
        logging.info("--- Stage 3: Finished ---")

def handle_historical_update(args, global_config):
    config_path = 'historical_update_config.json'
    
    # 1. Check if config exists
    if not os.path.exists(config_path):
        logging.warning(f"'{config_path}' not found. Generating a template based on codex_config keys...")
        
        # Mirror local_data_paths from global_config
        local_paths = global_config.get('local_data_paths', {})
        template = {
            "_notice": "You can use %archive% to point to the source_archives directory. Example: %archive%/1.3.0.0__t.zip/survival",
            "local_data_paths": {key: "" for key in local_paths.keys()}
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2)
        
        print("\n" + "!"*60)
        print(f"!!! TEMPLATE GENERATED: {config_path}")
        print("!!! Please fill in the correct base paths for the historical version.")
        print("!!! If a path key is left blank, any spec using that source_key will be skipped.")
        print("!"*60 + "\n")
        return

    # 2. Load config and override global_config
    with open(config_path, 'r', encoding='utf-8') as f:
        update_config = json.load(f)

    logging.info(f"--- Running Historical Update for version {args.version} ---")
    
    historical_paths = update_config.get('local_data_paths', {})
    archive_base = os.path.abspath('source_archives')
    
    for key, path in historical_paths.items():
        if path and path != "":
            # Substitute %archive%
            if "%archive%" in path:
                path = path.replace("%archive%", archive_base)
            
            global_config['local_data_paths'][key] = os.path.expandvars(path)
            logging.info(f"Overriding local_data_path '{key}' with: {global_config['local_data_paths'][key]}")
    
    # 3. Resolve specs to run
    config_dir = 'configs'
    all_spec_names = [f.replace('.yaml', '') for f in os.listdir(config_dir) if f.endswith('.yaml')]
    if args.spec:
        spec_names = [args.spec]
    else:
        spec_names = all_spec_names

    uploader = WikiUploader()
    
    for spec_name in spec_names:
        spec = load_spec(spec_name)
        if not spec: continue
        
        # Check if any source used by this spec relies on a blank key in historical config
        skip_spec = False
        spec_sources = spec.get('sources', [])
        for s in spec_sources:
            if s.get('type') == 'local_file':
                s_key = s.get('source_key')
                # If the key was provided in the historical config but is blank, skip it.
                if s_key in historical_paths and historical_paths[s_key] == "":
                    logging.info(f"Skipping spec '{spec_name}' because source_key '{s_key}' is blank in historical config.")
                    skip_spec = True
                    break
        
        if skip_spec: continue

        # Run Stages 1 & 2
        run_processing_pipeline(spec_name, 'resolve', global_config)
        
        # Run Stage 4 (Upload Data ONLY)
        logging.info(f"--- Uploading DATA ONLY for '{spec_name}' (Version {args.version}) ---")
        uploader.upload('data', args.version, spec_name=spec_name, is_historical=True)

    logging.info("--- Historical Update Pipeline finished ---")

def main():
    parser = argparse.ArgumentParser(description="Wiki Data Pipeline.")
    parser.add_argument('--spec', type=str, help='The name of the specification file to run.')
    parser.add_argument('--all-specs', action='store_true', help='Run the specified action for all spec files.')
    parser.add_argument('--action', type=str, choices=['collect', 'resolve', 'generate-modules', 'upload', 'full', 'historical-update'], default='full', help='The action to perform.')
    parser.add_argument('--upload-target', type=str, choices=['data', 'modules', 'maps', 'templates', 'all'], default='all', help="Specify what to upload.")
    parser.add_argument('--version', type=str, help='A specific version string (e.g., game version) for the upload.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging output.')

    args = parser.parse_args()

    # --- Logging Setup ---
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- Config Loading ---
    try:
        with open('codex_config.yaml', 'r') as f:
            global_config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.error("codex_config.yaml not found. Please create it.")
        return

    if global_config.get('local_data_paths'):
        for key, path in global_config['local_data_paths'].items():
            global_config['local_data_paths'][key] = os.path.expandvars(path)

    # --- Main Pipeline Execution ---
    if args.action == 'historical-update':
        if not args.version:
            logging.error("'historical-update' requires a --version to be specified.")
            return
        handle_historical_update(args, global_config)
        return

    if args.action != 'upload':
        if args.all_specs:
            config_dir = 'configs'
            all_specs = [f.replace('.yaml', '') for f in os.listdir(config_dir) if f.endswith('.yaml')]
            for spec_name in all_specs:
                run_processing_pipeline(spec_name, args.action, global_config)
        elif args.spec:
            run_processing_pipeline(args.spec, args.action, global_config)
        else:
            parser.print_help()
            return

    # --- Upload Stage ---
    if args.action in ['upload', 'full']:
        if not args.version:
            logging.error("The 'upload' or 'full' action requires a --version to be specified.")
            return
        
        logging.info("--- Stage 4: Starting Upload ---")
        uploader = WikiUploader()
        uploader.upload(args.upload_target, args.version, spec_name=args.spec)
        logging.info("--- Stage 4: Finished ---")

    # --- Archival Stage ---
    if args.action in ['collect', 'resolve', 'generate-modules', 'full'] and args.version:
        logging.info("--- Starting Automatic Archival ---")
        archive_version_sources(args.version, global_config)
        logging.info("--- Archival Stage Finished ---")

    logging.info("--- Pipeline finished ---")

if __name__ == "__main__":
    main()