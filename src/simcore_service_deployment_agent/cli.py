"""
Module that contains the command line app.

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -msimcore_service_deployment_agent` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``simcore_service_deployment_agent.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``simcore_service_deployment_agent.__main__`` in ``sys.modules``.

"""
import argparse
import asyncio
import json
import logging
import os
import sys

from environs import Env

from . import application, cli_config
from .git_url_watcher import GitUrlWatcher

log = logging.getLogger(__name__)


def create_environ(skip_system_environ=False):
    """
    Build environment of substitutable variables

    """
    # system's environment variables
    environ = {} if skip_system_environ else dict(os.environ)

    # project-related environment variables
    here = os.path.dirname(__file__)
    environ["THIS_PACKAGE_DIR"] = here

    # rootdir = search_osparc_repo_dir(start=here)
    # if rootdir is not None:
    #     environ['OSPARC_SIMCORE_REPO_ROOTDIR'] = str(rootdir)

    return environ


def setup(_parser):
    cli_config.add_cli_options(_parser)
    return _parser


parser = argparse.ArgumentParser(description="Command description.")
setup(parser)


def parse(args, _parser):
    """Parse options and returns a configuration object"""
    if args is None:
        args = sys.argv[1:]

    # ignore unknown options
    options, _ = _parser.parse_known_args(args)
    config = cli_config.config_from_options(options, vars=create_environ())

    # TODO: check whether extra options can be added to the config?!
    return config


def main(config=None):
    ####
    ### D E P L O Y M E N T   A G E N T
    ####
    env = Env()
    # 1. Logging
    log_level = env("LOG_LEVEL", "INFO")  # Default is info if nothing is set
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="[%(asctime)s] %(levelname)s: {%(pathname)s:%(lineno)d} - %(message)s",
    )
    logging.getLogger().setLevel(getattr(logging, log_level))
    # 2. Fetch config-file
    config_file_source = env("CONFIG_FILE_SOURCE", "git")  # Default is file
    if config_file_source == "git":
        # CONFIG_FILE_GIT_USER = env("CONFIG_FILE_GIT_USER")
        # CONFIG_FILE_GIT_PASS = env("CONFIG_FILE_GIT_PASS")
        CONFIG_FILE_GIT_URL = env("CONFIG_FILE_GIT_URL")
        CONFIG_FILE_GIT_BRANCH = env("CONFIG_FILE_GIT_BRANCH")
        CONFIG_FILE_GIT_PATH = env("CONFIG_FILE_GIT_PATH")
        git_repo_config = {
            "id": "deployement_agent_main_config",
            "url": CONFIG_FILE_GIT_URL,
            "branch": CONFIG_FILE_GIT_BRANCH,
            "pull_only_files": False,
            "username": "",
            "password": "",
            "paths": [CONFIG_FILE_GIT_PATH],
            "workdir": ".",
            "command": "sleep 1",
        }
        git_repo = GitUrlWatcher(git_repo_config)
        asyncio.run(git_repo.init())
        print(git_repo.watched_repo)
        config = parse(
            ["--config", git_repo.watched_repo.directory + "/" + CONFIG_FILE_GIT_PATH],
            parser,
        )
    else:
        log.error("Config wrong - no git repo for config file specified")
        exit(1)

    log.debug("We read the following configuration:")
    log.debug(json.dumps(config, indent=4, sort_keys=True))
    application.run(config)
