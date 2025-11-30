import os
import json
import logging
import re


def _sanitize_group_id(name):
    """
    Sanitizes a string to be used as a group ID.
    """
    
    if not name:
        return None
    return re.sub(r'[^a-zA-Z0-9_]', '', name.replace(' ', '_'))


def _process_survival_icons(resolved_data, staging_dir, template_path):
    """
    Generates creature groups for maps.
    """
    logging.info("Processing map data for 'survival_icons'...")
    with open(template_path, 'r', encoding='utf-8') as f:
        output_data = json.load(f)
    unique_creatures = {}
    
    for spawner in resolved_data:
        for creature in spawner.get('creatures', []):
            creature_id = creature.get('creature_id')
            
            if creature_id and creature_id not in unique_creatures:
                unique_creatures[creature_id] = creature
    groups = {}
    
    for creature_id, creature in unique_creatures.items():
        name_en = creature.get('name_en', f'Creature {creature_id}')
        group_id = _sanitize_group_id(name_en)
        
        if group_id:
            groups[group_id] = {
                "name": name_en,
                "icon": "IconMapMarkEnemy.png",
                "size": [50, 50]
            }
    output_data['groups'] = groups
    output_filename = os.path.basename(template_path)
    output_path = os.path.join(staging_dir, output_filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent='\t')
    logging.info(f"Generated and staged map JSON: {output_filename}")


def _process_simulation_room(resolved_data, staging_dir, template_path):
    """
    Processes data for the Simulation Room map.
    """
    logging.info("Processing map data for 'simulation_room'...")
    logging.debug(f"Total spawners received: {len(resolved_data)}")
    with open(template_path, 'r', encoding='utf-8') as f:
        output_data = json.load(f)
    markers = {}
    
    for i, spawner in enumerate(resolved_data):
        spawner_id = spawner.get('spawner_id')
        logging.debug(f"--- Processing spawner {i+1}/{len(resolved_data)}: ID {spawner_id} ---")
        static_territories_world1 = [t for t in spawner.get('static_territory', []) if str(t.get('world_type')) == '1']
        biome_territories_world1 = [t for t in spawner.get('biome_territory', []) if str(t.get('world_type')) == '1']
        logging.debug(f"Spawner {spawner_id}: Found {len(static_territories_world1)} static territories and {len(biome_territories_world1)} biome territories in world 1.")
        
        if not static_territories_world1 and not biome_territories_world1:
            logging.debug(f"Spawner {spawner_id}: Skipping, not in world 1.")
            continue
        logging.debug(f"Spawner {spawner_id}: Processing as it belongs to world 1.")
        all_positions = []
        all_positions.extend(spawner.get('spawn_positions', []))
        all_positions.extend(static_territories_world1)
        logging.debug(f"Spawner {spawner_id}: Total positions to process: {len(all_positions)}")
        
        for creature in spawner.get('creatures', []):
            name_en = creature.get('name_en', f'Creature {creature.get("creature_id")}')
            group_id = _sanitize_group_id(name_en)
            logging.debug(f"Spawner {spawner_id}: Processing creature '{name_en}' with group ID '{group_id}'")
            
            if not group_id:
                logging.debug(f"Spawner {spawner_id}: Skipping creature with no group ID.")
                continue
            
            if group_id not in markers:
                markers[group_id] = []
            
            for pos in all_positions:
                lon = pos.get('x')
                lat = pos.get('z')
                
                if lon is not None and lat is not None:
                    marker_data = {
                        "name": name_en,
                        "description": f"Spawner ID: {spawner_id}",
                        "lon": lon,
                        "lat": lat,
                    }
                    markers[group_id].append(marker_data)
                    logging.debug(f"Spawner {spawner_id}: Added marker for group '{group_id}' at lon={lon}, lat={lat}")
                else:
                    logging.debug(f"Spawner {spawner_id}: Skipping position due to missing coordinates: {pos}")
    logging.debug(f"Final markers dictionary: {json.dumps(markers, indent=2)}")
    output_data['markers'] = markers
    output_filename = os.path.basename(template_path)
    output_path = os.path.join(staging_dir, output_filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent='\t')
    logging.info(f"Generated and staged map JSON: {output_filename}")


def generate_json_maps(spec_name, resolved_data, global_config):
    logging.info(f"--- Generating JSON maps for {spec_name} ---")
    template_base_dir = "src/generators/templates"
    map_template_dir = os.path.join(template_base_dir, "map")
    staging_dir = "staging/maps"
    os.makedirs(staging_dir, exist_ok=True)
    
    if spec_name == 'map_location_spec':
        if os.path.exists(map_template_dir):
            for template_file in os.listdir(map_template_dir):
                if template_file.endswith(".json"):
                    template_name = template_file.replace('.json', '')
                    full_template_path = os.path.join(map_template_dir, template_file)
                    
                    if template_name == 'simulation_room':
                        _process_simulation_room(resolved_data, staging_dir, full_template_path)
                    elif template_name == 'survival_icons':
                        _process_survival_icons(resolved_data, staging_dir, full_template_path)
                    else:
                        logging.warning(f"No specific processor for map template: {template_file}")
