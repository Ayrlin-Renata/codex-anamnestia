import os
import importlib
import logging
import json
from src.utils.config_loader import load_spec
from src.transformers.standardizer import standardize_source
from src.resolver import resolve_data

class PipelineRunner:
    """
    Encapsulates the data extraction and resolution stages for reuse.
    """
    def __init__(self, global_config):
        self.global_config = global_config

    def get_extractor(self, type_name):
        if type_name == 'local_file':
            module_name = 'src.extractors.local_file_extractor'
            class_name = 'LocalFileExtractor'
        elif type_name == 'cdn':
            module_name = 'src.extractors.cdn_extractor'
            class_name = 'CdnExtractor'
        else:
            module_name = f"src.extractors.{type_name}_extractor"
            class_name = f"{type_name.capitalize()}Extractor"
        
        try:
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logging.error(f"Could not load extractor {class_name} from {module_name}: {e}")
            raise

    def run_spec(self, spec_name, skip_resolution=False):
        """
        Runs Stage 1 and Stage 2 for a single specification.
        Returns (all_data, resolved_objects)
        """
        logging.info(f"--- [PipelineRunner] Processing '{spec_name}' ---")
        
        spec = load_spec(spec_name)
        if not spec:
            logging.error(f"Specification '{spec_name}' not found.")
            return None, None

        # --- Stage 1: Extraction & Standardization ---
        all_data = {}
        for source_spec in spec.get('sources', []):
            source_name = source_spec['name']
            source_type = source_spec['type']
            
            if source_type == 'manual':
                raw_data = source_spec['data']
            else:
                try:
                    ExtractorClass = self.get_extractor(source_type)
                    extractor = ExtractorClass()
                    raw_data = extractor.extract(source_spec, self.global_config)
                except Exception as e:
                    logging.error(f"Failed to run extractor for type '{source_type}'. {e}")
                    continue

            all_data[source_name] = standardize_source(raw_data, source_spec)
        
        if skip_resolution:
            return all_data, None

        # --- Stage 2: Resolution ---
        resolved_objects = []
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
            resolved_objects = resolve_data(spec, all_data, master_id_set)
        else:
            primary_source_name = spec.get('primary_source')
            primary_data = all_data.get(primary_source_name, {})
            items_to_process = []
            for item_or_list in primary_data.values():
                if isinstance(item_or_list, list):
                    items_to_process.extend(item_or_list)
                else:
                    items_to_process.append(item_or_list)
            resolved_objects = resolve_data(spec, all_data, items_to_process)
            
        return all_data, resolved_objects
