import os
import json
import logging
import shutil
import yaml


def to_lua_table(obj, indent=2):
    """
    Naively converts a Python object to a Lua table string.
    """
    
    if isinstance(obj, dict):
        parts = []
        
        for key, value in obj.items():
            if isinstance(key, str) and key.isidentifier():
                key_str = key
            else:
                key_str = f'["{key}"]'
            parts.append(f'{" " * (indent + 2)}{key_str} = {to_lua_table(value, indent + 2)}')
        return '{\n' + ',\n'.join(parts) + '\n' + ' ' * indent + '}'
    elif isinstance(obj, list):
        parts = [to_lua_table(item, indent + 2) for item in obj]
        return '{\n' + ',\n'.join(parts) + '\n' + ' ' * indent + '}'
    else:
        return json.dumps(obj, ensure_ascii=False)


def generate_lua_modules(spec_name, resolved_data, global_config):
    logging.info(f"--- Generating Lua modules for {spec_name} ---")
    template_base_dir = "src/generators/templates"
    util_template_dir = os.path.join(template_base_dir, "util")
    ui_template_dir = os.path.join(template_base_dir, "ui")
    staging_dir = "staging/modules"
    os.makedirs(staging_dir, exist_ok=True)
    spec_base_name = spec_name.replace('_spec', '')
    # Stage spec-specific or shared utility modules
    if os.path.exists(util_template_dir):
        for f in os.listdir(util_template_dir):
            if f.endswith('.lua'):
                shutil.copy(os.path.join(util_template_dir, f), os.path.join(staging_dir, f))
                logging.info(f"Staged utility module: {f}")

    # Stage spec-specific or shared UI modules
    if os.path.exists(ui_template_dir):
        for f in os.listdir(ui_template_dir):
            if f.endswith('.lua'):
                shutil.copy(os.path.join(ui_template_dir, f), os.path.join(staging_dir, f))
                logging.info(f"Staged UI module: {f}")

    # Stage general utils.lua from the base template dir
    utils_template_path = os.path.join(template_base_dir, "utils.lua")
    if os.path.exists(utils_template_path):
        shutil.copy(utils_template_path, os.path.join(staging_dir, "utils.lua"))
        logging.info("Staged general utils module: utils.lua")

    # Generate link_common.lua from link_rules.yaml
    generate_link_common(template_base_dir, staging_dir)

    wikitemplates_dir = os.path.join(template_base_dir, "wikitemplates")
    staging_wikitemplates_dir = "staging/wikitemplates"
    os.makedirs(staging_wikitemplates_dir, exist_ok=True)
    
    # Load shared templates from upload_config.yaml
    upload_config_path = "configs/upload_config.yaml"
    shared_templates = []
    if os.path.exists(upload_config_path):
        with open(upload_config_path, 'r', encoding='utf-8') as f:
            u_config = yaml.safe_load(f)
            shared_templates = u_config.get('shared_templates', [])

    if os.path.exists(wikitemplates_dir):
        spec_keywords = [kw for kw in spec_base_name.lower().split('_') if len(kw) > 3]
        for f in os.listdir(wikitemplates_dir):
            if f.endswith('.wikitext'):
                is_shared = f in shared_templates
                is_match = is_shared or (spec_base_name in f.lower()) or \
                           any(kw in f.lower() for kw in spec_keywords)
                
                if is_match:
                    shutil.copy(os.path.join(wikitemplates_dir, f), os.path.join(staging_wikitemplates_dir, f))
                    logging.info(f"Staged wikitext template: {f}")

def generate_link_common(template_base_dir, staging_dir):
    rules_path = "configs/link_rules.yaml"
    template_path = os.path.join(template_base_dir, "util/link_common.lua")
    output_path = os.path.join(staging_dir, "link_common.lua")
    
    if not os.path.exists(rules_path) or not os.path.exists(template_path):
        logging.warning("Skipping link_common generation: link_rules.yaml or template missing.")
        return

    logging.info("Generating link_common.lua from rules...")
    with open(rules_path, 'r', encoding='utf-8') as f:
        rules_data = yaml.safe_load(f)
    
    rules_dict = {r['context']: r for r in rules_data.get('rules', [])}
    lua_rules_table = to_lua_table(rules_dict, indent=0)
    
    # Simple table formatting fix for top level
    lua_rules_table = lua_rules_table.strip('{}').strip()

    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    final_content = template_content.replace("-- [[RULES_PLACEHOLDER]]", lua_rules_table)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    logging.info("Staged generated module: link_common.lua")
