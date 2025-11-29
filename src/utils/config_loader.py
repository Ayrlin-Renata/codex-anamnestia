import yaml


def load_spec(spec_name):
    """
    Loads a specification file from the configs directory.
    """
    path = f"configs/{spec_name}.yaml"
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
