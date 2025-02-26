import os
import importlib.util
import logging
import inspect

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def available_functions(modules_path="modules"):
    """
    Returns a dictionary of available modules and their user-defined functions.
    Filters out non-user-defined functions and internal methods.
    """
    functions_by_module = {}

    if not os.path.exists(modules_path):
        logger.error(f"❌ Modules directory '{modules_path}' not found.")
        return functions_by_module

    logger.info(f"Scanning for modules in '{modules_path}'...")

    for file in os.listdir(modules_path):
        if file.endswith(".py") and file != "__init__.py":
            module_name = os.path.splitext(file)[0]
            module_path = os.path.join(modules_path, file)

            try:
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                collected_functions = []
                # Collect only user-defined functions in the module
                for name, obj in inspect.getmembers(module, inspect.isfunction):
                    if obj.__module__ == module.__name__:
                        collected_functions.append(name)

                if collected_functions:
                    functions_by_module[module_name] = collected_functions
                    logger.info(f"✅ Loaded module: {module_name} | Functions: {collected_functions}")

            except Exception as e:
                logger.error(f"❌ Failed to load module '{module_name}': {e}")

    return functions_by_module
