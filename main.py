from util import Task, Workflow, get_latest_release, get_module_path, log, Status
import click
import subprocess
from pathlib import Path
import os
import signal
from time import sleep
from logger import logger

NAME_SPACE="siibra-violet"
CONFIG_PATH_KEY="CONFIG_PATH_KEY"

class ConfigTask(Task):
    name="config_task"
    
    def __init__(self, config, *args, latest_version=None, **kwargs) -> None:
        super().__init__(*args, latest_version=latest_version, **kwargs)
        self.config=config

    def pre(self, *args, **kwargs):
        config_path=get_module_path(self.config or f"siibra-{self.latest_version}", "https://jugit.fz-juelich.de/t.dickscheid/brainscapes-configurations.git")
        self.keyval[CONFIG_PATH_KEY]=config_path

class SpyTask(Task):
    name="spy_task"

    def __init__(self, spy, *args, latest_version=None, **kwargs) -> None:
        super().__init__(*args, latest_version=latest_version, **kwargs)
        self.spy=spy
    
    def pre(self):
        super().pre()
        spy_path = get_module_path(self.spy or f"v{self.latest_version}", "https://github.com/FZJ-INM1-BDA/siibra-python.git")
        self.spy_path = spy_path
    
    def run(self):
        subprocess.run(["pip", "install", "-e", self.spy_path], stdout=log(f"{NAME_SPACE}-siibra-python.log"), stderr=subprocess.STDOUT)

class SapiTask(Task):
    name="sapi_task"

    def __init__(self, sapi: str, *args, latest_version=None, **kwargs) -> None:
        super().__init__(*args, latest_version=latest_version, **kwargs)
        self.sapi=sapi
        self.cleanup_api=None
        self.sapi_path: str=None
    
    def pre(self):
        latest_sapi=None
        if self.sapi is None:
            latest_sapi_release=get_latest_release("fzj-inm1-bda", "siibra-api")
            latest_sapi=latest_sapi_release.get("tag_name")
        sapi_path=get_module_path(self.sapi or latest_sapi, "https://github.com/fzj-inm1-bda/siibra-api.git")
        self.sapi_path=sapi_path

    
    def should_run(self, workflow: Workflow):
        logger.debug(f"{self.name} checking should run")
        config_cloned = self.keyval[CONFIG_PATH_KEY] is not None

        # must check spy is already installed. 
        # Otherwise siibra-api will attempt to install siibra from pypi
        spy_tasks = [ task for task in workflow.tasks if task.name == SpyTask.name ]
        assert len(spy_tasks) == 1, f"Expecting one an donly one spy_task, but got {len(spy_tasks)}"
        spy_installed = (spy_tasks[0].status == Status.SUCCESS)
        logger.debug(f"{self.name} should run: {config_cloned and spy_installed}")
        return config_cloned and spy_installed
    
    def run(self):
        subprocess.run(["pip", "install", "-r", Path(self.sapi_path) / "requirements" / "all.txt" ], stdout=log(f"{NAME_SPACE}-siibra-api.log"), stderr=subprocess.STDOUT)
        subprocess.run(["docker", "pull", "redis"], stdout=log(f"{NAME_SPACE}-redis-pull.log"), stderr=subprocess.STDOUT)
    
        # First, start redis instance, 
        subprocess.Popen(["docker", "run",
                        "-it",
                        "-p", "127.0.0.1:6379:6379",
                        "--rm",
                        "--name", f"{NAME_SPACE}-redis",
                        "redis"],
                        stdout=log(f"{NAME_SPACE}-redis.log"),
                        stderr=subprocess.STDOUT)
        self.cleanup_cb.append(lambda: subprocess.run([ "docker", "stop", f"{NAME_SPACE}-redis" ], stdout=log(f"{NAME_SPACE}-redis.log"), stderr=subprocess.STDOUT))

        # Now, start the uvicorn instance
        api_process=subprocess.Popen(["uvicorn", "api.server:api", "--port", "10081"], cwd=self.sapi_path, start_new_session=True, env={
            **os.environ,
            "SIIBRA_USE_CONFIGURATION": self.keyval[CONFIG_PATH_KEY],
        }, stdout=log(f"{NAME_SPACE}-siibra-api.log"), stderr=subprocess.STDOUT)
        self.cleanup_cb.append(lambda: api_process.send_signal(signal.SIGTERM))

class SxplrNodeTask(Task):
    name="sxplr_node_task"

    def __init__(self, sxplr, *args, latest_version=None, **kwargs) -> None:
        super().__init__(*args, latest_version=latest_version, **kwargs)
        sxplr_path=get_module_path(sxplr, "https://github.com/fzj-inm1-bda/siibra-explorer.git")
        self.sxplr_path=sxplr_path
    
    def pre(self):
        
        def process_sxplr_env(line: str):
            return line.lstrip().lstrip("/") if "endpoint-local-10081" in line else f"// {line}"
            
        path_to_env = Path(self.sxplr_path, "src/environments/environment.common.ts")
        with open(path_to_env, "r") as fp:
            original_lines = fp.readlines()
            new_lines = [
                process_sxplr_env(line) if "endpoint" in line else line
                for line in original_lines
            ]
        with open(path_to_env, "w") as fp:
            fp.write("".join(new_lines))

        def spxlr_env_cleanup():
            with open(path_to_env, "w") as fp:
                fp.write("".join(original_lines))
        self.cleanup_cb.append(spxlr_env_cleanup)
        
        subprocess.run(["npm", "i"], cwd=self.sxplr_path, stdout=log(f"{NAME_SPACE}-siibra-explorer-install.log"), stderr=subprocess.STDOUT)
    
    def run(self):
        sxplr_process = subprocess.Popen(["./node_modules/.bin/ng", "serve"], cwd=self.sxplr_path, start_new_session=True, stdout=log(f"{NAME_SPACE}-siibra-explorer.log"), stderr=subprocess.STDOUT)
        def kill_npm_process():
            sxplr_process.send_signal(signal.SIGTERM)
        self.cleanup_cb.append(kill_npm_process)

class SxplrDockerTask(Task):
    name="sxplr_docker_task"
    DOCKER_TAG = "docker-registry.ebrains.eu/siibra/siibra-explorer:master-local-10081"
    SXPLR_DOCKER_CONTAINER_NAME = "sxplr-container"
    
    def __init__(self, *args, latest_version=None, **kwargs) -> None:
        super().__init__(*args, latest_version=latest_version, **kwargs)
    
    def pre(self):
        subprocess.run(["docker", "pull", self.DOCKER_TAG], stdout=log(f"{NAME_SPACE}-siibra-explorer-pull.log"), stderr=subprocess.STDOUT)
    
    def run(self):
        subprocess.run(["docker", "run",
                        "-p", "127.0.0.1:8080:8080",
                        "--name", self.SXPLR_DOCKER_CONTAINER_NAME,
                        "--rm",
                        "-dit",
                        self.DOCKER_TAG],
                        stdout=log(f"{NAME_SPACE}-siibra-explorer.log"),
                        stderr=subprocess.STDOUT)
        def terminate_docker():
            subprocess.run(["docker", "stop", self.SXPLR_DOCKER_CONTAINER_NAME])
        self.cleanup_cb.append(terminate_docker)


@click.command()
@click.option("--config", help="Path to local config, or commit'ish on main repo. Default to latest release.")
@click.option("--spy", help="Path to local siibra-python repo, or version tag, or commit'ish on main repo. Default to latest release.")
@click.option("--sapi", help="Path to local siibra-api, or version tag, or commit'ish on main repo. Default to latest release.")
@click.option("--sxplr", help="Path to local siibra-explorer, or version tag, or commit'ish on main repo. Default to latest release.")
@click.option("--debug", help="Show debug logs", default=False)
def main(config, spy, sapi, sxplr, debug):

    if debug:
        logger.setLevel("DEBUG")
    
    latest_version=None
    if config is None or spy is None:
        latest_release=get_latest_release("fzj-inm1-bda", "siibra-python")
        latest_tag: str=latest_release.get("tag_name")
        assert latest_tag
        latest_version=latest_tag.lstrip("v")

    workflow=Workflow()
    
    config_task=ConfigTask(config, latest_version=latest_version)
    workflow.register_task(config_task)
    
    spy_task = SpyTask(spy, latest_version=latest_version)
    workflow.register_task(spy_task)

    sapi_task = SapiTask(sapi, latest_version=latest_version)
    workflow.register_task(sapi_task)

    sxplr_task = SxplrNodeTask(sxplr, latest_version=latest_version) if sxplr else SxplrDockerTask(latest_version=latest_version)
    workflow.register_task(sxplr_task)

    workflow.run()

if __name__ == "__main__":
    main()