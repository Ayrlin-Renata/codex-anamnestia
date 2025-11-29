import os
import json
import logging
import shutil


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
            parts.append(f'{{' ' * (indent + 2)}{key_str} = {to_lua_table(value, indent + 2)}')
        return '{{\n' + ',\n'.join(parts) + '\n' + ' ' * indent + '}'
    elif isinstance(obj, list):
        parts = [to_lua_table(item, indent + 2) for item in obj]
        return '{{\n' + ',\n'.join(parts) + '\n' + ' ' * indent + '}'
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
    spec_util_filename = f"{spec_base_name}_util.lua"
    spec_util_template_path = os.path.join(util_template_dir, spec_util_filename)
    
    if os.path.exists(spec_util_template_path):
        shutil.copy(spec_util_template_path, os.path.join(staging_dir, spec_util_filename))
        logging.info(f"Staged spec-specific util module: {spec_util_filename}")
    spec_ui_filename = f"{spec_base_name}_ui.lua"
    spec_ui_template_path = os.path.join(ui_template_dir, spec_ui_filename)
    
    if os.path.exists(spec_ui_template_path):
        shutil.copy(spec_ui_template_path, os.path.join(staging_dir, spec_ui_filename))
        logging.info(f"Staged spec-specific ui module: {spec_ui_filename}")
    utils_template_path = os.path.join(template_base_dir, "utils.lua")
    utils_staged_path = os.path.join(staging_dir, "utils.lua")
    
    if os.path.exists(utils_template_path) and not os.path.exists(utils_staged_path):
        shutil.copy(utils_template_path, utils_staged_path)
        logging.info("Staged general utils module: utils.lua")
