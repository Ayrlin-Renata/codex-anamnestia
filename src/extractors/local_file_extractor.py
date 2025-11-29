import os
import importlib
import json
import logging


class LocalFileExtractor:
    """
    Extracts data from local, potentially encrypted, game files.
    """
    def extract(self, source_info, base_paths):
        source_type_path = source_info.get('path_type', 'default')
        relative_path = source_info['path']
        base_path = base_paths.get(source_type_path)
        
        if not base_path:
            logging.error(f"No path configured for path_type '{source_type_path}' in codex_config.yaml")
            return None
        path = os.path.join(base_path, relative_path)
        logging.info(f"Extracting data from local file: {path}")
        try:
            with open(path, 'rb') as f:
                file_bytes = f.read()
        except FileNotFoundError:
            logging.error(f"File not found at {path}")
            return None
        
        decoder_type = source_info.get('decoder')
        
        if not decoder_type:
            logging.error(f"No decoder specified for source with path {path}")
            return None
        try:
            decoder_module = importlib.import_module('src.utils.decoder')
            decoder_func = getattr(decoder_module, decoder_type)
            decoded_obj = decoder_func(file_bytes)
            
            if decoded_obj:
                output_dir = "data/decoded"
                os.makedirs(output_dir, exist_ok=True)
                base_filename = os.path.basename(relative_path)
                output_filename = os.path.splitext(base_filename)[0] + ".json"
                output_path = os.path.join(output_dir, output_filename)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(decoded_obj, f, indent=2, ensure_ascii=False)
                logging.debug(f"Saved decoded file to {output_path}")
            return decoded_obj.get('list', decoded_obj)
        except (AttributeError, ImportError):
            logging.error(f"Could not find decoder function '{decoder_type}' in src.utils.decoder")
            return None
        except Exception as e:
            logging.error(f"Decoder '{decoder_type}' failed for file {path}. Reason: {e}")
            return None
