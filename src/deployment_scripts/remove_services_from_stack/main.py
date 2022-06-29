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
listOfServicesToDrop = [i for i in env.str("EXCLUDED_SERVICES").split(",")]
#
with open(env.str("FILENAME_IN"), "r+") as stackfile:
    stackfileDict = yaml.full_load(stackfile)
    assert "services" in stackfileDict
    for i in list(stackfileDict["services"]):
        if i in listOfServicesToDrop:
            try:
                stackfileDict["services"].pop(i)
            except KeyError as ex:
                pass
    print(json.dumps(stackfileDict, sort_keys=True, indent=4))
