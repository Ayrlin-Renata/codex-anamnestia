"""
This module is responsible for transforming raw extracted data into a standardized,
lookup-friendly format for the resolver.

It supports multiple strategies, such as creating a unique-key lookup map (dictionary)
or grouping items by a common key for one-to-many relationships.
"""
from collections import defaultdict


def create_lookup_map(data, key_field):
    """
    Transforms a list of objects into a dict keyed by a unique field.
    """
    return {item.get(key_field): item for item in data}


def create_grouping_map(data, key_field):
    """
    Transforms a list of objects into a dict where each key maps to a list of items.
    """
    grouped_data = defaultdict(list)
    
    for item in data:
        key = item.get(key_field)
        
        if key is not None:
            grouped_data[key].append(item)
    return dict(grouped_data)


def standardize_source(source_data, source_spec):
    """ 
    Standardizes raw data based on the strategy defined in the source's specification.
    """
    strategy = source_spec.get('strategy', 'lookup')
    key = source_spec.get('key')
    print(f"Standardizing source '{source_spec['name']}' with strategy '{strategy}'")
    
    if strategy == 'group_by':
        if not key:
            raise ValueError(f"Strategy 'group_by' requires a 'key' in source spec '{source_spec['name']}'.")
        return create_grouping_map(source_data, key)
    
    if key:
        return create_lookup_map(source_data, key)
    return source_data
