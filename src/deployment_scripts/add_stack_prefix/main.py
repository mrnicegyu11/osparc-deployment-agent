import json

# This script iterates a stack.yml file and subsitutes the images of the docker services with those matching a given GIT_SHA of a release
# Images not belonging to the organization specified are not subsituted
import yaml

# ENV
from environs import Env

env = Env()
env.read_env("./.env", recurse=False)
#
#
with open(env.str("FILENAME_IN"), "r+") as stackfile:
    stackfileDict = yaml.full_load(stackfile)
    assert "services" in stackfileDict
    new_services = {}
    services_prefix = env.str("SERVICES_PREFIX")
    services_prefix_delim = env.str("SERVICES_PREFIX_DELIM")
    for service_name in list(stackfileDict["services"]):
        new_service_name = f"{services_prefix}{services_prefix_delim}{service_name}"
        new_services[new_service_name] = stackfileDict["services"][service_name]
    stackfileDict["services"] = new_services
    print(json.dumps(stackfileDict, sort_keys=True, indent=4))
