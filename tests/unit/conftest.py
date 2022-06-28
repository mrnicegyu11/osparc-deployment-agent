# pylint:disable=redefined-outer-name

import re
from random import randint
from typing import Any, Dict

import faker
import pytest
from aioresponses import aioresponses
from aioresponses.core import CallbackResult

from simcore_service_deployment_agent import auto_deploy_task

fake = faker.Faker()


@pytest.fixture(scope="session")
def bearer_code() -> str:
    FAKE_BEARER_CODE = "TheBearerCode"
    return FAKE_BEARER_CODE


@pytest.fixture()
def aioresponse_mocker() -> aioresponses:
    PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]
    with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        yield mock


@pytest.fixture()
async def mattermost_service_mock(
    aioresponse_mocker: aioresponses, valid_config: Dict[str, Any]
) -> aioresponses:
    get_channels_pattern = (
        re.compile(
            rf'{valid_config["main"]["notifications"][0]["url"]}/api/v4/channels/.+'
        )
        if "notifications" in valid_config["main"]
        else re.compile(".*")
    )
    aioresponse_mocker.get(
        get_channels_pattern, status=200, payload={"header": "some text in the header"}
    )
    aioresponse_mocker.put(
        get_channels_pattern, status=200, payload={"success": "bravo"}
    )
    aioresponse_mocker.post(
        f'{valid_config["main"]["notifications"][0]["url"]}/api/v4/posts'
        if "notifications" in valid_config["main"]
        else "...",
        status=201,
        payload={"success": "bravo"},
    )

    yield aioresponse_mocker


@pytest.fixture()
def mocked_cmd_utils(mocker):
    mock_run_cmd_line = mocker.patch.object(
        auto_deploy_task,
        "run_cmd_line_unsafe",
        return_value="",
    )
    yield mock_run_cmd_line
