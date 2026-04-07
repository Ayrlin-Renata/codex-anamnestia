import importlib
import logging

class VirtualExtractor:
    """
    Extracts data dynamically by invoking a custom python generator function.
    This allows specifications to include synthetic data sources generated at runtime.
    """
    def extract(self, source_info, config):
        generator_name = source_info.get('generator')
        module_name = source_info.get('module', 'src.generators.virtual_generators')
        
        if not generator_name:
            logging.error(f"No generator specified for virtual source in spec.")
            return None
            
        logging.info(f"Running virtual generator '{generator_name}' from '{module_name}'")
        try:
            module = importlib.import_module(module_name)
            generator_func = getattr(module, generator_name)
            return generator_func(config)
        except AttributeError:
            logging.error(f"Could not find function '{generator_name}' in {module_name}")
            return None
        except ImportError:
            logging.error(f"Could not load module {module_name}")
            return None
        except Exception as e:
            logging.error(f"Failed to run virtual generator '{generator_name}': {e}")
            return None
