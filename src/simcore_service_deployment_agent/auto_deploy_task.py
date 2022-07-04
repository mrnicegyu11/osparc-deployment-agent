import asyncio
import logging
from asyncio.exceptions import CancelledError
from typing import Dict, Tuple

from aiohttp import ClientSession, web
from aiohttp.client import ClientTimeout
from servicelib.application_keys import APP_CONFIG_KEY

from simcore_service_deployment_agent.exceptions import CmdLineError

from .app_state import State
from .cmd_utils import run_cmd_line_unsafe
from .git_url_watcher import GitUrlWatcher, GitUrlWatcherGroup
from .notifier import notify, notify_state

log = logging.getLogger(__name__)
TASK_NAME = __name__ + "_autodeploy_task"
TASK_SESSION_NAME = __name__ + "session"


RETRY_WAIT_SECS = 2  ##TODO: As Env Var
RETRY_COUNT = 10  # TODO: As Env var
AUTO_DEPLOY_FAILURE_RETRY_SLEEP = 300  # TODO: As Env var


async def create_git_watch_subtask(app_config: Dict) -> Tuple[GitUrlWatcher, Dict]:
    log.debug("creating git repo watch subtask")
    listOfGitUrlWatchers = [
        GitUrlWatcher(i) for i in app_config["main"]["watched_git_repositories"]
    ]
    git_sub_task = GitUrlWatcherGroup(listOfGitUrlWatchers)
    descriptions = await git_sub_task.init()
    return (git_sub_task, descriptions)


async def deploy_update_stacks(app_config: Dict, git_task: GitUrlWatcherGroup):
    if app_config["main"]["deployed_version"] != "":
        # Assert that all watches repos have the matching version present in branch or tag
        for repo in git_task.watched_repos:
            if repo.watched_repo.branch_regex != "":
                # repo get branches
                # filter by regex
                # find matching branch
                # check out branch

                ####
                # Here, create the branch-name to be checked out by substituting the
                ####
                await repo.checkout_branch(app_config["main"]["deployed_version"])
                await repo.pull()
                # Run command

            elif repo.watched_repo.tags_regex != "":
                # (repo assert correct branch checkout)
                # repo get tags
                # find matching tag
                # check out tag
                await repo.pull()
                await repo.checkout_tag(app_config["main"]["deployed_version"])
                # Run command
                # Restore state?
            else:
                # TODO: Handle autoupdate of given branch
                changes = await repo.check_for_changes()
                if changes != {}:
                    # Update
                    try:
                        await run_cmd_line_unsafe(
                            cmd=repo.watched_repo.command,
                            cwd_=repo.watched_repo.workdir,
                        )
                        current_git_repo_config = next(
                            (
                                x
                                for x in app_config["main"]["watched_git_repositories"]
                                if x.id == repo.watched_repo.id
                            ),
                            None,
                        )
                        if current_git_repo_config:
                            if current_git_repo_config.exitCodeOnCommandSuccess:
                                exit(current_git_repo_config.exitCodeOnCommandSuccess)
                        else:
                            raise CmdLineError(
                                "Something went wrong."
                            )  # FIXME: Better error statement
                    except CmdLineError:
                        log.error(
                            "Failed to run command: %s ", " && ".join(repo.command)
                        )
                        log.error("Aborting deployment!")
                        break
            try:
                await run_cmd_line_unsafe(
                    cmd=repo.watched_repo.command, cwd_=repo.watched_repo.workdir
                )
            except CmdLineError:
                log.error(
                    "Failed to run command: %s ", " && ".join(repo.watched_repo.command)
                )
                log.error("Aborting deployment!")
                break
            # Check out the tag everywhere: How would this work with the git_url_watcher?
            # Run command everywhere
    else:
        for repo in git_task.watched_repos:
            changes = await repo.check_for_changes()
            if changes != {}:
                # Update
                try:
                    await run_cmd_line_unsafe(
                        cmd=repo.watched_repo.command, cwd_=repo.watched_repo.workdir
                    )
                except CmdLineError:
                    log.error(
                        "Failed to run command: %s ",
                        " && ".join(repo.watched_repo.command),
                    )
                    log.error("Aborting deployment!")
                    break
    return


async def _deploy(
    app: web.Application,
) -> GitUrlWatcherGroup:
    try:
        log.info("starting stack deployment...")
        # get configs
        app["state"][TASK_NAME] = State.STARTING
        app_config = app[APP_CONFIG_KEY]
        app_session = app[TASK_SESSION_NAME]
        # create initial stack
        git_task, descriptions = await create_git_watch_subtask(app_config)
        # deploy stack to swarm
        # TODO: Time this call, exceed polling interval to 5min
        await deploy_update_stacks(app_config, git_task)  # TODO: Code
        # notifications
        await notify(
            app_config,
            app_session,
            message=f"Stack deployed with:\n{list(descriptions.values())}",
        )
        # TODO: Notification is wrong I guess
        main_repo = app_config["main"]["docker_stack_recipe"]["workdir"]
        await notify_state(
            app_config,
            app_session,
            state=app["state"][TASK_NAME],
            message=descriptions[main_repo] if main_repo in descriptions else "",
        )
        log.info("stack (re-)deployed")
        return git_task
    except asyncio.CancelledError:
        log.info("task cancelled")
        raise


async def auto_deploy(app: web.Application):
    log.info("start autodeploy task")
    app_config = app[APP_CONFIG_KEY]
    app_session = app[TASK_SESSION_NAME]
    # Check config
    for repo in app_config["main"]["watched_git_repositories"]:
        if (
            (
                repo["branch_regex"] == ""
                and repo["tags_regex"] == ""
                and repo["branch"] == ""
            )
            or (repo["branch_regex"] != "" and repo["tags_regex"] != "")
            or (repo["branch_regex"] != "" and repo["branch"] == "")
        ):
            raise RuntimeError("Wrong repo config for repo ", repo.watched_repo.id)
    # init
    try:
        await _deploy(app)
    except CancelledError:
        app["state"][TASK_NAME] = State.STOPPED
        return
    except Exception:  # pylint: disable=broad-except
        log.exception("Error while initializing deployment: ", exc_info=True)
        # this will trigger a restart from the docker swarm engine
        app["state"][TASK_NAME] = State.FAILED
        return
    # loop forever to detect changes
    while True:
        try:
            app["state"][TASK_NAME] = State.RUNNING
            await _deploy(app)
            sleepInterval = app_config["main"]["polling_interval"]
            log.debug("Sleeping for ", sleepInterval, "seconds...")
            await asyncio.sleep(sleepInterval)
        except asyncio.CancelledError:
            log.info("cancelling task...")
            app["state"][TASK_NAME] = State.STOPPED
            break
        except Exception as exc:  # pylint: disable=broad-except
            # some unknown error happened, let's wait 5 min and restart
            log.exception("Task error:")
            if app["state"][TASK_NAME] != State.PAUSED:
                app["state"][TASK_NAME] = State.PAUSED
                await notify_state(
                    app_config,
                    app_session,
                    state=app["state"][TASK_NAME],
                    message=str(exc),
                )
            sleepInterval = AUTO_DEPLOY_FAILURE_RETRY_SLEEP
            log.debug("Sleeping for ", AUTO_DEPLOY_FAILURE_RETRY_SLEEP, "seconds...")
            await asyncio.sleep(AUTO_DEPLOY_FAILURE_RETRY_SLEEP)
        finally:
            # cleanup the subtasks
            log.info("task completed...")


def setup(app: web.Application):
    app.cleanup_ctx.append(persistent_session)
    try:
        app.cleanup_ctx.append(background_task)
    except asyncio.CancelledError:
        print("We encountered an error in running the deployment agent:")


async def background_task(app: web.Application):
    app["state"] = {TASK_NAME: State.STARTING}
    app[TASK_NAME] = asyncio.get_event_loop().create_task(auto_deploy(app))
    yield
    task = app[TASK_NAME]
    task.cancel()
    await task


async def persistent_session(app):
    async with ClientSession(timeout=ClientTimeout(5)) as session:
        app[TASK_SESSION_NAME] = session
        yield


__all__ = ["setup"]
