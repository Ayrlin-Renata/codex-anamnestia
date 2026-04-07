import os
import json
import logging
import yaml

def generate_missing_items(config):
    """
    Synthesizes item definitions for IDs that exist in drop tables but are missing
    from the primary item master tables. Uses raw JSONs extracted from local files.
    """
    def load_source(filename_base):
        # We need to find the file in the configured survival path
        survival_base = config.get('local_data_paths', {}).get('survival', os.path.join("data", "survival"))
        
        # Candidate directories to check. The extracted path or its internal 'survival' subfolder.
        search_dirs = [survival_base, os.path.join(survival_base, "survival")]
        
        for base in search_dirs:
            if not os.path.isdir(base): continue
            
            # Try JSON FIRST (already decoded)
            json_path = os.path.join(base, filename_base + ".json")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data.get('list', data)
                return data
                
            # Try DAT (legacy/archive)
            dat_path = os.path.join(base, filename_base + ".dat")
            if os.path.exists(dat_path):
                from src.utils.decoder import decode_survival_dat
                with open(dat_path, 'rb') as f:
                    data = decode_survival_dat(f.read())
                if isinstance(data, dict):
                    return data.get('list', data)
                return data
            
        return []

    virtual_items = []
    
    try:
        common_items = load_source("master_item_common") or []
        harvestables = load_source("master_harvestable_object") or []
        drops = load_source("master_dropitem_for_harvestable_object") or []
        
        known_item_ids = {i.get('itemId') for i in common_items if i.get('itemId') is not None}
        
        # Load unified manual texts for objects
        manual_names = {}
        manual_base = config.get('local_data_paths', {}).get('manual', os.path.join("data", "manual"))
        path = os.path.join(manual_base, "breakable_names.json")
        
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                manual_names = {item['id']: item for item in data}
        
        # Build lookup tool for harvestable object by dropId
        obj_by_drop_group = {o.get('dropId'): o for o in harvestables if o.get('dropId')}
        
        synthesized_ids = set()
        
        for drop in drops:
            item_id = drop.get('itemId')
            
            if item_id and item_id not in known_item_ids and item_id not in synthesized_ids and item_id != 0:
                drop_group = drop.get('dropGroup')
                obj = obj_by_drop_group.get(drop_group)
                
                name_en, name_ja, desc_en, desc_ja = "Unknown Virtual Drop", "Unknown Virtual Drop", "", ""
                icon = None
                category_id = 10102 # Default guess
                
                if obj:
                    name_for_tool = obj.get('nameForTool')
                    # Resolving the hardcoded manual name mapped by 'nameForTool' string
                    if name_for_tool:
                        manual = manual_names.get(name_for_tool, {})
                        name_en = manual.get('name_en', name_for_tool)
                        name_ja = manual.get('name_ja', name_for_tool)
                    icon = obj.get('iconResourceName')
                
                virtual_items.append({
                    "id": item_id,
                    "category_id": category_id,
                    "sort_id": 5, 
                    "category_name_en": "Vegetables",
                    "category_name_ja": "野菜",
                    "icon_resource_name": icon,
                    "name_en": name_en,
                    "name_ja": name_ja,
                    "description_en": desc_en,
                    "description_ja": desc_ja
                })
                synthesized_ids.add(item_id)
                
        logging.info(f"Virtual Source Generator: Synthesized {len(virtual_items)} missing items from local JSON caches.")
        return virtual_items
        
    except Exception as e:
        logging.error(f"Error generating missing items from local JSON: {e}")
        return []
