import argparse
import os
import importlib
import yaml
import json
import logging

from src.utils.config_loader import load_spec
from src.generators.lua_module_generator import generate_lua_modules
from src.generators.json_map_generator import generate_json_maps
from src.generators.changelog_generator import ChangelogGenerator
from src.uploaders.wiki_uploader import WikiUploader
from src.utils.archiver import archive_version_sources, get_latest_archive
from src.utils.pipeline_runner import PipelineRunner


def run_processing_pipeline(spec_name, action, global_config):
    logging.info(f"--- Running processing for '{spec_name}' ---")
    
    spec = load_spec(spec_name)
    if not spec:
        logging.error(f"Specification '{spec_name}' not found or is empty.")
        return

    # --- Stage 1 & 2: Extraction, Standardization & Resolution ---
    all_data = {}
    resolved_objects = []

    if action in ['collect', 'resolve', 'generate-modules', 'full']:
        runner = PipelineRunner(global_config)
        all_data, resolved_objects = runner.run_spec(spec_name, skip_resolution=(action == 'collect'))
        
        if action == 'collect': return
        
        if resolved_objects:
            output_dir = "staging/outputs"
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
    config_path = 'configs/historical_update_config.yaml'
    
    # 1. Check if config exists
    if not os.path.exists(config_path):
        logging.warning(f"'{config_path}' not found. Generating a template based on codex_config keys...")
        
        # Mirror local_data_paths from global_config
        local_paths = global_config.get('local_data_paths', {})
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write("# You can use %archive% to point to the source_archives directory.\n")
            f.write("# Example: %archive%/1.3.0.0__t.zip/survival\n")
            yaml.dump({"local_data_paths": {key: "" for key in local_paths.keys()}}, f, indent=2)
        
        print("\n" + "!"*60)
        print(f"!!! TEMPLATE GENERATED: {config_path}")
        print("!!! Please fill in the correct base paths for the historical version.")
        print("!!! If a path key is left blank, any spec using that source_key will be skipped.")
        print("!"*60 + "\n")
        return

    # 2. Load config and override global_config
    with open(config_path, 'r', encoding='utf-8') as f:
        update_config = yaml.safe_load(f)

    logging.info(f"--- Running Historical Update for version {args.version} ---")
    global_config['is_historical'] = True
    
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
    config_dir = 'configs/specs'
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

def run_changelog_task(args, global_config, current_archive=None):
    """Execution wrapper for ChangelogGenerator."""
    can_proceed = args.version or args.changelog_historical or (args.changelog_v1 and args.changelog_v2)
    
    if not can_proceed:
        logging.warning("Changelog: version, historical flag, or explicit v1/v2 paths are required.")
        return

    generator = ChangelogGenerator(global_config)
    v1 = args.changelog_v1
    v2 = args.changelog_v2
    label_1 = v1 or "Unknown"
    label_2 = v2 or "Current State"

    if not v1:
        if args.changelog_historical:
            config_path = 'configs/historical_update_config.yaml'
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    v1 = yaml.safe_load(f)
                label_1 = "Historical Config"
            else:
                logging.warning("Changelog: historical_update_config.yaml not found.")
                return
        else:
            # The baseline is the archive BEFORE the current one
            v1 = get_latest_archive(args.version, fallback=True, skip_path=current_archive)
            if not v1:
                logging.info(f"Changelog: No existing archives found for version {args.version}. Skipping.")
                return
            label_1 = os.path.basename(v1)

    if not v2:
        if current_archive:
            # Current state is the archive we just created/confirmed
            v2 = current_archive
            label_2 = os.path.basename(current_archive)
        else:
            v2 = global_config
            label_2 = "Current Local State"
    
    output_dir = "staging/outputs/changelog"
    generator.generate(v1, v2, output_dir, label_1, label_2)

def main():
    parser = argparse.ArgumentParser(description="Wiki Data Pipeline.")
    parser.add_argument('--spec', type=str, help='The name of the specification file to run.')
    parser.add_argument('--all-specs', action='store_true', help='Run the specified action for all spec files.')
    parser.add_argument('--action', type=str, choices=['collect', 'resolve', 'generate-modules', 'upload', 'full', 'historical-update', 'changelog'], default='full', help='The action to perform.')
    parser.add_argument('--upload-target', type=str, choices=['data', 'modules', 'maps', 'templates', 'all'], default='all', help="Specify what to upload.")
    parser.add_argument('--version', type=str, help='A specific version string (e.g., game version) for the upload.')
    parser.add_argument('--force-upload', action='store_true', help='Force upload even if the version is not newer than the online meta.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging output.')
    
    # Changelog arguments
    parser.add_argument('--changelog', action='store_true', help='Generate a changelog between current state and last archive.')
    parser.add_argument('--changelog-historical', action='store_true', help='Compare current state against historical_update_config.yaml.')
    parser.add_argument('--changelog-v1', type=str, help='Override first comparison version (ZIP path or base directory).')
    parser.add_argument('--changelog-v2', type=str, help='Override second comparison version (ZIP path or base directory).')

    args = parser.parse_args()

    # --- Logging Setup ---
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- Config Loading ---
    try:
        config_path = os.path.abspath('configs/codex_config.yaml')
        with open(config_path, 'r') as f:
            global_config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.error("codex_config.yaml not found. Please create it.")
        return

    if global_config.get('local_data_paths'):
        for key, path in global_config['local_data_paths'].items():
            global_config['local_data_paths'][key] = os.path.expandvars(path)

    # --- Main Pipeline Execution ---
    if args.action == 'changelog':
        logging.info("--- Starting Dedicated Changelog Generation ---")
        current_archive = None
        if args.version:
            current_archive = archive_version_sources(args.version, global_config)
        run_changelog_task(args, global_config, current_archive=current_archive)
        logging.info("--- Pipeline finished ---")
        return

    if args.action == 'historical-update':
        if not args.version:
            logging.error("'historical-update' requires a --version to be specified.")
            return
        handle_historical_update(args, global_config)
        return

    if args.action != 'upload':
        if args.all_specs:
            config_dir = 'configs/specs'
            all_specs = [f.replace('.yaml', '') for f in os.listdir(config_dir) if f.endswith('.yaml')]
            for spec_name in all_specs:
                run_processing_pipeline(spec_name, args.action, global_config)
        elif args.spec:
            run_processing_pipeline(args.spec, args.action, global_config)
        elif not (args.changelog or args.changelog_historical or args.changelog_v1 or args.changelog_v2):
            parser.print_help()
            return

    # --- Upload Stage ---
    if args.action in ['upload', 'full']:
        if args.version:
            logging.info("--- Stage 4: Starting Upload ---")
            uploader = WikiUploader()
            uploader.upload(args.upload_target, args.version, spec_name=args.spec, force_upload=args.force_upload)
            logging.info("--- Stage 4: Finished ---")
        elif not (args.changelog or args.changelog_historical or args.changelog_v1 or args.changelog_v2):
            logging.error("The 'upload' or 'full' action requires a --version to be specified.")
            return
        else:
            logging.info("No version specified and changelog flags present. Skipping upload stage.")

    # --- Archival Stage (runs FIRST so changelog can use the result) ---
    current_archive = None
    if args.action in ['collect', 'resolve', 'generate-modules', 'full'] and args.version:
        logging.info("--- Starting Automatic Archival ---")
        current_archive = archive_version_sources(args.version, global_config)
        logging.info("--- Archival Stage Finished ---")

    # --- Changelog Stage ---
    if (args.action == 'full' or args.changelog or args.changelog_historical or 
        args.changelog_v1 or args.changelog_v2):
        logging.info("--- Starting Automatic Changelog Generation ---")
        run_changelog_task(args, global_config, current_archive=current_archive)
        logging.info("--- Changelog Stage Finished ---")


    logging.info("--- Pipeline finished ---")

if __name__ == "__main__":
    main()