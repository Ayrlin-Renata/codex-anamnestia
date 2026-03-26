import os
import zipfile
import hashlib
import logging
import datetime
import shutil
from src.utils.config_loader import load_spec

def get_file_hash(path):
    """Calculates SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def archive_version_sources(version, global_config):
    """
    Identifies all file-based sources for all specs, compares them against 
    the most recent archive for the version, and creates a new ZIP if changed.
    """
    archive_dir = "source_archives"
    os.makedirs(archive_dir, exist_ok=True)
    
    # 1. Collect all unique file sources from all specs
    config_dir = 'configs'
    all_specs = [f.replace('.yaml', '') for f in os.listdir(config_dir) if f.endswith('.yaml')]
    
    file_mapping = {} # zip_rel_path -> abs_path
    local_paths = global_config.get('local_data_paths', {})
    
    for spec_name in all_specs:
        spec = load_spec(spec_name)
        if not spec: continue
        
        for source in spec.get('sources', []):
            s_type = source.get('type')
            if s_type == 'local_file':
                s_key = source.get('path_type') or source.get('source_key')
                relative_path = source.get('path')
            elif s_type == 'manual':
                continue # Skip manual data (embedded in spec)
            else:
                # Generic handling for file-backed extractors (like cdn)
                s_key = s_type
                relative_path = source.get('path')
                # Optional: Handle .json suffix if it's likely a JSON-based extractor
                if relative_path and s_type == 'cdn' and not relative_path.endswith('.json'):
                    relative_path += ".json"
            
            base_path = local_paths.get(s_key)
            if base_path and relative_path:
                abs_path = os.path.join(base_path, relative_path)
                # Normalize for zip path
                zip_rel_path = f"{s_key}/{relative_path}".replace('\\', '/')
                if os.path.exists(abs_path):
                    file_mapping[zip_rel_path] = abs_path
                else:
                    logging.warning(f"Archiver: Source file not found: {abs_path}")
            else:
                logging.debug(f"Archiver: Skipping source '{source.get('name')}' - missing path_type or path.")

    if not file_mapping:
        logging.info("Archiver: No local files found to archive.")
        return

    # 2. Get the latest archive for this version
    existing_archives = [f for f in os.listdir(archive_dir) if f.startswith(f"{version}__") and f.endswith(".zip")]
    existing_archives.sort(reverse=True)
    
    current_hashes = {rel: get_file_hash(abs_p) for rel, abs_p in file_mapping.items()}
    
    should_archive = True
    if existing_archives:
        latest_archive = os.path.join(archive_dir, existing_archives[0])
        logging.info(f"Archiver: Comparing against latest archive: {latest_archive}")
        
        try:
            with zipfile.ZipFile(latest_archive, 'r') as z:
                archived_files = z.namelist()
                # Check if all current files exist and have the same hash
                # Note: We can't easily get hashes from zip without extracting or storing them.
                # We'll extract to a temp dir and compare hashes.
                temp_compare_dir = os.path.join(archive_dir, "_temp_compare")
                os.makedirs(temp_compare_dir, exist_ok=True)
                
                match = True
                if len(archived_files) != len(file_mapping):
                    match = False
                else:
                    for rel in file_mapping.keys():
                        if rel not in archived_files:
                            match = False
                            break
                        z.extract(rel, temp_compare_dir)
                        archived_hash = get_file_hash(os.path.join(temp_compare_dir, rel))
                        if archived_hash != current_hashes[rel]:
                            match = False
                            break
                
                shutil.rmtree(temp_compare_dir)
                if match:
                    logging.info(f"Archiver: Sources for version {version} are identical to the latest archive. Skipping.")
                    should_archive = False
        except Exception as e:
            logging.error(f"Archiver: Error comparing archive: {e}")
            should_archive = True

    # 3. Create a new archive if needed
    if should_archive:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        new_archive_name = f"{version}__{timestamp}.zip"
        new_archive_path = os.path.join(archive_dir, new_archive_name)
        
        logging.info(f"Archiver: Creating new archive: {new_archive_path}")
        with zipfile.ZipFile(new_archive_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for rel, abs_p in file_mapping.items():
                z.write(abs_p, rel)
        logging.info("Archiver: Archival complete.")
