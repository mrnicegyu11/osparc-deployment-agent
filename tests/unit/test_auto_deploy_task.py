# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=bare-except

import asyncio
from asyncio import Future
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterator

import aioresponses
import pytest
import yaml
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses

# Monkeypatch the tenacity wait time https://stackoverflow.com/questions/47906671/python-retry-with-tenacity-disable-wait-for-unittest
from tenacity.wait import wait_none

from simcore_service_deployment_agent import auto_deploy_task
from simcore_service_deployment_agent.app_state import State
from simcore_service_deployment_agent.application import create
from simcore_service_deployment_agent.git_url_watcher import GitUrlWatcher


@pytest.fixture()
def mocked_git_url_watcher(mocker) -> Dict[str, Any]:
    mock_git_changes = {
        "init": mocker.patch.object(GitUrlWatcher, "init", return_value={}),
        "check_for_changes": mocker.patch.object(
            GitUrlWatcher, "check_for_changes", return_value={}
        ),
    }
    return mock_git_changes


@pytest.fixture(scope="session")
def mock_stack_config() -> Dict[str, Any]:
    cfg = {
        "version": "3.7",
        "services": {
            "fake_service": {"image": "fake_image"},
            "fake_service2": {"image": "fake_image"},
        },
    }
    return cfg


@pytest.fixture()
def mocked_stack_file(
    valid_config: Dict[str, Any], mock_stack_config: Dict[str, Any]
) -> Iterator[Path]:
    file_name = Path(valid_config["main"]["docker_stack_recipe"]["stack_file"])
    with file_name.open("w", encoding="utf-8") as fp:
        yaml.safe_dump(mock_stack_config, fp)
    yield file_name
    file_name.unlink()


@pytest.fixture
def client(
    loop: asyncio.AbstractEventLoop,
    aiohttp_unused_port: Callable[[], int],
    aiohttp_client: Callable[..., Awaitable[TestClient]],
    valid_config: Dict[str, Any],
    monkeypatch,
) -> Iterator[TestClient]:
    # increase the speed to fail
    monkeypatch.setattr(auto_deploy_task, "RETRY_COUNT", 2)
    monkeypatch.setattr(auto_deploy_task, "RETRY_WAIT_SECS", 1)

    app = create(valid_config)
    server_kwargs = {"port": aiohttp_unused_port(), "host": "localhost"}

    client = loop.run_until_complete(aiohttp_client(app, server_kwargs=server_kwargs))
    yield client


def test_client(client: TestClient):
    # check that the client starts/stops correctly
    pass


async def test_wait_for_dependencies_no_portainer_up(client: TestClient):
    assert client.app  # nosec
    # wait for the app to start
    while client.app["state"][auto_deploy_task.TASK_NAME] == State.STARTING:
        await asyncio.sleep(1)
    assert client.app["state"][auto_deploy_task.TASK_NAME] == State.FAILED


async def test_setup_task(
    mocked_git_url_watcher,
    mocked_cmd_utils,
    mocked_stack_file,
    mattermost_service_mock: aioresponses,
    client: TestClient,
):
    assert client.app
    assert auto_deploy_task.TASK_NAME in client.app
    while client.app["state"][auto_deploy_task.TASK_NAME] == State.STARTING:
        await asyncio.sleep(1)
    # assert client.app["state"][auto_deploy_task.TASK_NAME] == State.RUNNING #TODO: Reenable
