import yaml
from dotenv import load_dotenv
import argparse


if __name__ == "__main__":

    load_dotenv()
    parser = argparse.ArgumentParser(description = 'Example with non-optional arguments')
    
    parser.add_argument('customer', action = "store")
    parser.add_argument('entity', action = "store")

    customer_input = parser.parse_args().customer
    entity_input = parser.parse_args().entity


    print(customer_input,entity_input )