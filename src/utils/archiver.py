import os
import json
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

def collect_file_mapping(global_config):
    """Collects all unique file sources from all specs and maps them to zip paths."""
    config_dir = 'configs/specs'
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
                continue
            else:
                s_key = s_type
                relative_path = source.get('path')
                if relative_path and s_type == 'cdn' and not relative_path.endswith('.json'):
                    relative_path += ".json"
            
            base_path = local_paths.get(s_key)
            if base_path and relative_path:
                # Ensure environment variables and user tilde are expanded
                base_path = os.path.expanduser(os.path.expandvars(base_path))
                abs_path = os.path.join(base_path, relative_path)
                zip_rel_path = f"{s_key}/{relative_path}".replace('\\', '/')
                if os.path.exists(abs_path):
                    file_mapping[zip_rel_path] = abs_path
    return file_mapping

def is_archive_identical(archive_path, file_mapping):
    """Compares the current file mapping against an existing archive, normalizing JSON/text."""
    if not os.path.exists(archive_path): return False
    try:
        with zipfile.ZipFile(archive_path, 'r') as z:
            archived_files = z.namelist()
            if len(archived_files) != len(file_mapping):
                logging.debug(f"Archiver: Count mismatch for {archive_path}")
                return False
            for rel, abs_p in file_mapping.items():
                if rel not in archived_files: return False
                try:
                    z_raw = z.read(rel)
                    with open(abs_p, 'rb') as f:
                        l_raw = f.read()
                    
                    if rel.endswith('.json'):
                        z_data = json.loads(z_raw.decode('utf-8'))
                        l_data = json.loads(l_raw.decode('utf-8'))
                        if z_data != l_data:
                            logging.debug(f"Archiver: JSON content mismatch for {rel}")
                            return False
                    else:
                        # Normalize line endings for text files
                        z_text = z_raw.decode('utf-8').replace('\r\n', '\n')
                        l_text = l_raw.decode('utf-8').replace('\r\n', '\n')
                        if z_text != l_text:
                            logging.debug(f"Archiver: Text mismatch for {rel}")
                            return False
                except (UnicodeDecodeError, json.JSONDecodeError):
                    # Fallback to bitwise
                    if hashlib.sha256(z_raw).hexdigest() != get_file_hash(abs_p):
                        return False
        return True
    except Exception as e:
        logging.error(f"Archiver: Error comparing archive {archive_path}: {e}")
        return False

def archive_version_sources(version, global_config):
    """
    Identifies all file-based sources for all specs, compares them against 
    the most recent archive for the version, and creates a new ZIP if changed.
    Returns the path of the current archive (existing if identical, new otherwise).
    Returns None if no files found.
    """
    archive_dir = "source_archives"
    os.makedirs(archive_dir, exist_ok=True)
    
    file_mapping = collect_file_mapping(global_config)
    if not file_mapping:
        logging.info("Archiver: No local files found to archive.")
        return None

    # Get the latest archive for this version
    existing_archives = sorted([f for f in os.listdir(archive_dir) if f.startswith(f"{version}__") and f.endswith(".zip")], reverse=True)
    
    if existing_archives and is_archive_identical(os.path.join(archive_dir, existing_archives[0]), file_mapping):
        logging.info(f"Archiver: Sources for version {version} are identical to the latest archive. Skipping.")
        return os.path.join(archive_dir, existing_archives[0])

    # Create a new archive
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    new_archive_name = f"{version}__{timestamp}.zip"
    new_archive_path = os.path.join(archive_dir, new_archive_name)
    
    logging.info(f"Archiver: Creating new archive: {new_archive_path}")
    with zipfile.ZipFile(new_archive_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel, abs_p in file_mapping.items():
            z.write(abs_p, rel)
    logging.info("Archiver: Archival complete.")
    return new_archive_path

def get_latest_archive(version=None, fallback=True, skip_path=None):
    """
    Returns the path to the most recent archive.
    If skip_path is provided, skips that specific archive (used to skip the 'current' one).
    """
    archive_dir = "source_archives"
    if not os.path.exists(archive_dir): return None
        
    skip_substrings = ["1.3.0.0", "version__asarai", "___temp"]
    all_archives = sorted([f for f in os.listdir(archive_dir) if f.endswith(".zip") and not any(s in f for s in skip_substrings)], reverse=True)
    if not all_archives: return None

    # Candidates: (is_version_match, filename). Prioritize version matches.
    candidates = sorted([(version and f.startswith(f"{version}__"), f) for f in all_archives], key=lambda x: (x[0], x[1]), reverse=True)

    for is_version, name in candidates:
        if not is_version and not fallback: continue
        full_path = os.path.join(archive_dir, name)
        if skip_path and os.path.abspath(full_path) == os.path.abspath(skip_path):
            logging.info(f"Archiver: Skipping current archive {name} for baseline comparison.")
            continue
        return full_path
    
    return None
