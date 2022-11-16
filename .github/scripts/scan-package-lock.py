#!/bin/python

import json
import os
import requests
import logging
import yaml

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ../../package-json.lock
PACKAGE_LOCK_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(__file__))), 'package-lock.json')
CLIENT_ID = os.environ.get("PORT_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PORT_CLIENT_SECRET")
RUNTIME = os.environ.get("RUNTIME")
MICROSERVICE_NAME=os.environ.get("MICROSERVICE_NAME")

API_URL = 'https://api.getport.io/v1'


# This function uses pName and pVer to create a dict object for a package entity.
# The replace()'s format the problematic 'id' characters, while the Title keeps the original format of the package identity
def create_package_entity_json(pName, pVer):
    # identifier cannot contain '.'
    format_version = pVer.replace(".", "_").replace('^', '')
    format_name = pName.replace(".", "_").replace('/', '-').replace('@', '')
    package_entity = {
        "identifier": f"{format_name}-{format_version}",
        "title": f"{pName}_{pVer}",
        "blueprint": "Package",
        "properties": {
            "version": f"{pVer}"
        },
        "relations": {}
    }
    return package_entity


def get_port_api_token():
    """
    Get a Port API access token
    This function uses CLIENT_ID and CLIENT_SECRET from config
    """

    credentials = {'clientId': CLIENT_ID, 'clientSecret': CLIENT_SECRET}

    token_response = requests.post(
        f"{API_URL}/auth/access_token", json=credentials)

    return token_response.json()['accessToken']


def report_to_port(blueprint, entity_json, token):
    '''
    Reports to Port on a new entity based on provided ``entity_props``
    '''

    headers = {
        'Authorization': f'Bearer {token}'
    }
    params = {
        'upsert': 'true'
    }
    logger.info('Creating entity:')
    print(json.dumps(entity_json, indent=4))
    logger.info(json.dumps(entity_json))
    response = requests.post(f'{API_URL}/blueprints/{blueprint}/entities',
                             json=entity_json, headers=headers, params=params)
    logger.info(response.status_code)
    logger.info(json.dumps(response.json()))
    print(response.json())
    return response.status_code


def get_port_entity(blueprint, id, token):
    '''
    Gets Port entity using blueprint and id
    '''
    logger.info('Fetching token')
    token = get_port_api_token()

    headers = {
        'Authorization': f'Bearer {token}'
    }
    logger.info('Getting entity:')
    response = requests.get(
        f'{API_URL}/blueprints/{blueprint}/entities/{id}', headers=headers)
    logger.info(response.status_code)
    logger.info(json.dumps(response.json()))
    return response.json(), response.status_code


# Warps get_port_entity. Receives an id, and returns
# a DeploymentConfig entity with it's entity.relations.packages[] cleared.
def get_deploy_config(ms_name, runtime, token):
    """
    This function warps get_port_entity, and get specifically, a deployment config with the identifier
    'ms_name-RUNTIME'.

    Args:
                    ms_name (string): Microservice name
                    token (string): PortAPI token

    Returns:
                    dc_entity:
    """
    identifier = f"{ms_name}-{runtime}"
    deployment_config, status = get_port_entity(
        "DeploymentConfig", identifier, token)
    if status != 200 and status != 201:
        print(f"DeploymentConfig named {identifier} doesn't exist!")
        return None
    dc_entity = deployment_config["entity"]
    # Must supply title field
    if dc_entity['title'] is None:
        dc_entity['title'] = identifier
    # Remove old packages from deployment config
    dc_entity['relations']['package'].clear()
    return dc_entity


def main():
    token = get_port_api_token()
    with open(PACKAGE_LOCK_JSON_PATH) as f:
        json_dict = json.load(f)
    dc_entity = get_deploy_config(MICROSERVICE_NAME, RUNTIME, token)
    for package in json_dict['packages'][""]['dependencies']:
        print(package)
        print(f"Creating Package entities for {package}!")

        # For each microservice, create dependent package entities in port
        # In yarn.lock, dependencies only show minimum version
        package_ver = json_dict["packages"][f"node_modules/{package}"]["version"]
        print(package_ver)
        package_entity = create_package_entity_json(package, package_ver)
        report_to_port("Package", package_entity, token)
        print(
            f"Created {package.replace('.','_').replace('/','-')}-{package_ver.replace('.','_')} package!")
        # Add package to entities relation.package dictionary
        print(dc_entity)
        dc_entity['relations']['package'].append(
            f"{package.replace('.','_').replace('/','-').replace('@','')}-{package_ver.replace('.','_').replace('^','')}")
    report_to_port("DeploymentConfig", dc_entity, token)
    print(f"Updated {MICROSERVICE_NAME}-{RUNTIME} DeploymentConfig!")


main()