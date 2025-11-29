"""
Core data resolution engine.

This module takes standardized data sources and a specification config
to link and combine data into a final, resolved format. It uses a recursive
approach to build complex, nested output objects.
"""
import logging


def _get_value(context, rule, all_data, silent=False):
    """
    Helper to extract a value from the current data context, handling simple, direct, and chained linked lookups.
    """
    
    if 'link_key' in rule:
        source_name = rule['from']
        target_source = all_data.get(source_name)
        
        if target_source is None:
            if not silent: logging.warning(f"Source '{source_name}' not found in all_data.")
            return None
        lookup_key = _get_value(context, rule['link_key'], all_data, silent=True)
        
        if lookup_key is None:
            return None
        linked_item = target_source.get(lookup_key)
        
        if linked_item is None:
            return None
        
        if 'field' in rule:
            if isinstance(linked_item, dict):
                return linked_item.get(rule['field'])
            else:
                if not silent:
                    logging.warning(f"Rule expects a dictionary to get field '{rule['field']}', but linked item is a {type(linked_item)}.")
                return None
        else:
            return linked_item
    elif rule.get('from_context'):
        return context.get(rule['from_context'])
    elif rule.get('from_parent', False):
        if 'field' not in rule:
            return context
        return context.get(rule['field'])
    elif 'from' in rule:
        source_name = rule['from']
        source_object = context.get(source_name)
        
        if source_object and 'field' in rule:
            return source_object.get(rule['field'])
    
    if not silent: logging.warning(f"Could not resolve value for rule: {rule}")
    return None


def _check_condition(context, condition_rule, all_data):
    """
    Checks if a condition is met for a conditional sub-object.
    """
    source_to_check = all_data.get(condition_rule['source'], {})
    key_to_check = _get_value(context, condition_rule['key'], all_data, silent=True)
    
    if key_to_check is None:
        return False
    exists = key_to_check in source_to_check
    return exists if condition_rule.get('exists') else not exists


def _apply_transform(value, rule, all_data):
    """
    Applies a transformation to a retrieved value based on the spec rule.
    """
    transform_rule = rule.get('transform')
    
    if not transform_rule or value is None:
        return value
    transform_type = transform_rule.get('type')
    
    if transform_type == 'lookup':
        lookup_source_name = transform_rule.get('in_source')
        
        if not lookup_source_name:
            logging.warning(f"Transform 'lookup' is missing 'in_source'.")
            return value
        target_source = all_data.get(lookup_source_name, {})
        return target_source.get(value)
    
    if transform_type == 'split':
        delimiter = transform_rule.get('delimiter', ',')
        as_type = transform_rule.get('as_type', 'string')
        
        if not isinstance(value, str):
            logging.warning(f"Transform 'split' expected a string, but got {type(value)}. Returning original value.")
            return value
        split_values = value.split(delimiter)
        try:
            if as_type == 'int':
                return [int(v.strip()) for v in split_values if v.strip()]
            elif as_type == 'float':
                return [float(v.strip()) for v in split_values if v.strip()]
            else:
                return [v.strip() for v in split_values if v.strip()]
        except ValueError as e:
            logging.warning(f"Could not cast split value to '{as_type}'. {e}. Returning strings.")
            return [v.strip() for v in split_values if v.strip()]
    return value


def _resolve_simple_value(context, rule, all_data):
    """
    Resolves a simple value and applies transforms.
    """
    raw_value = _get_value(context, rule, all_data)
    return _apply_transform(raw_value, rule, all_data)


def _build_node(context, structure, all_data, level=0):
    """
    Recursively builds a node in the output tree based on the structure config.
    """
    output_node = {}
    
    for key, rule in structure.items():
        if 'condition' in rule:
            if not _check_condition(context, rule['condition'], all_data):
                continue
        logging.debug(f"Processing output field: '{key}' at level {level}")
        node_type = rule.get('type')
        
        if 'coalesce' in rule:
            logging.debug(f"  - Type: Coalesce")
            final_value = None
            
            for sub_rule in rule['coalesce']:
                value = _resolve_simple_value(context, sub_rule, all_data)
                
                if value is not None:
                    logging.debug(f"    - [SUCCESS] Found value using source '{sub_rule.get('from')}'.")
                    final_value = value
                    break
            
            if final_value is None:
                logging.debug(f"    - [FAIL] All coalesce options failed.")
            output_node[key] = final_value
        elif node_type == 'object':
            logging.debug(f"  - Type: Nested Object")
            
            if 'fields' not in rule:
                logging.error(f"Rule for object '{key}' is missing required 'fields' definition.")
                output_node[key] = None
            else:
                output_node[key] = _build_node(context, rule['fields'], all_data, level + 1)
        elif node_type == 'list':
            logging.debug(f"  - Type: List from '{rule.get('from')}'")
            lookup_key = _get_value(context, rule['link_key'], all_data)
            logging.debug(f"  - Generated list lookup key: '{lookup_key}'")
            target_source = all_data.get(rule['from'], {})
            linked_item = target_source.get(lookup_key)
            
            if 'field' in rule and isinstance(linked_item, dict):
                logging.debug(f"  - Extracting list from field '{rule['field']}' of linked object.")
                linked_list = linked_item.get(rule['field'], [])
            else:
                linked_list = linked_item if isinstance(linked_item, list) else []
            logging.debug(f"  - Found {len(linked_list)} items in list.")
            
            if 'sub_object' in rule:
                logging.debug(f"  - Building list of complex objects...")
                list_items = []
                
                for i, item in enumerate(linked_list):
                    logging.debug(f"  - Building sub-object {i+1}/{len(linked_list)}")
                    list_items.append(_build_node(item, rule['sub_object'], all_data, level + 1))
                output_node[key] = list_items
            else:
                logging.debug(f"  - Returning bare list as-is.")
                output_node[key] = linked_list
        else:
            output_node[key] = _resolve_simple_value(context, rule, all_data)
    return output_node


def resolve_data(spec, all_data, items_to_process):
    """ 
    Resolves data based on a specification.
    """
    logging.info("Starting hierarchical data resolution...")
    resolved_objects = []
    output_structure = spec['output_structure']
    is_union = spec.get('resolution_strategy') == 'union'
    logging.info(f"Processing {len(items_to_process)} items.")
    
    for i, item in enumerate(items_to_process):
        logging.debug(f"--- Resolving primary object {i+1}/{len(items_to_process)} ---")
        
        if is_union:
            context = {'union_id': item}
        else:
            context = {spec['primary_source']: item}
        resolved_obj = _build_node(context, output_structure, all_data)
        resolved_objects.append(resolved_obj)
    logging.info("Resolution complete.")
    return resolved_objects
