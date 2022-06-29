import copy
import json

import requests

# This script iterates a stack.yml file and subsitutes the images of the docker services with those matching a given GIT_SHA of a release
# Images not belonging to the organization specified are not subsituted
import yaml

# ENV
from environs import Env

env = Env()
env.read_env("./.env", recurse=False)
#
url = "https://hub.docker.com/v2/users/login/"
login_content = {
    "username": "devops4itis",
    "password": "383b1d1e-bf53-4750-b287-ce47cfd056a6",
}
session = requests.Session()
session.auth = (env.str("DOCKER_USERNAME"), env.str("DOCKER_PASSWORD"))
hed = {"Content-Type": "application/json"}
#
with open(env.str("FILENAME_IN"), "r+") as stackfile:
    stackfileDict = yaml.full_load(stackfile)
    stackfileDictMod = copy.deepcopy(stackfileDict)
    assert "services" in stackfileDict
    for i in stackfileDict["services"]:
        if (
            env.str("DOCKERHUB_ORG")
            in stackfileDict["services"][i]["image"].split("/")[0]
        ):
            imageTarget = (
                stackfileDict["services"][i]["image"].split("/")[1].split(":")[0]
            )
            # print(imageTarget,":")
            url = (
                "https://hub.docker.com/v2/repositories/"
                + str(env.str("DOCKERHUB_ORG"))
                + "/"
                + str(imageTarget)
                + "/tags/?page_size="
                + str(env.str("QUERY_PAGESIZE"))
            )
            r = session.get(url, headers=hed)
            if r.status_code == 200:
                # if "results" not in r.json():
                #    print(r.json())
                for j in r.json()["results"]:
                    if env.str("TARGET_GIT_SHA") in j["name"]:
                        stackfileDictMod["services"][i]["image"] = stackfileDict[
                            "services"
                        ][i]["image"].split("/")[0]
                        stackfileDictMod["services"][i]["image"] += "/"
                        stackfileDictMod["services"][i]["image"] = (
                            imageTarget + ":" + j["name"]
                        )
            else:
                print("ERROR: Request to dockerhub failed!")
                print(r.json())
                exit(1)
    print(json.dumps(stackfileDictMod, sort_keys=True, indent=4))
