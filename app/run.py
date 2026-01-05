import yaml
from dotenv import load_dotenv
import argparse
import sys
import importlib
from pathlib import Path

if __name__ == "__main__":

    load_dotenv()
    parser = argparse.ArgumentParser(description = 'Example with non-optional arguments')
    
    parser.add_argument('customer', action = "store")
    parser.add_argument('base', action = "store")
    parser.add_argument('entity', action = "store")

    customer = parser.parse_args().customer
    base = parser.parse_args().base
    entity = parser.parse_args().entity


    print(customer, base, entity)

    # ✅ Carpeta de salida
    out_dir = Path("/data") / customer / base
    out_dir.mkdir(parents=True, exist_ok=True)


    module_path = f"customers.{customer}.{base}.{entity}"

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        print(f"❌ No se encontró el módulo: {module_path}")
        sys.exit(1)

    if not hasattr(module, "run"):
        print(f"❌ El módulo {module_path} no tiene una función run()")
        sys.exit(1)

    print(f"▶ Ejecutando {module_path}.run()")
    print(f"▶ Ejecutando {module_path}.run(out_dir=...)")
    module.run(out_dir=str(out_dir), customer=customer, base=base, entity=entity)