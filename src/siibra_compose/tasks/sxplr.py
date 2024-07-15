import subprocess
from pathlib import Path
import signal
import os

from siibra_compose.util import PortedTask, get_module_path, log, Workflow
from siibra_compose.const import NAME_SPACE
from .sapi import SapiTask

class SxplrNodeTask(PortedTask):
    name="sxplr_node_task"

    def __init__(self, sxplr, *args, port=8080, **kwargs) -> None:
        super().__init__(*args, port=port, **kwargs)
        sxplr_path=get_module_path(sxplr, "https://github.com/fzj-inm1-bda/siibra-explorer.git")
        self.sxplr_path=sxplr_path

    def should_run(self, workflow: Workflow) -> bool:
        sapi_tasks = workflow.find_tasks(SapiTask)
        assert len(sapi_tasks) == 1, f"Expected one and only one siibra-api task to be run, but got {len(sapi_tasks)}"
        assert sapi_tasks[0].port == 10081, f"At the moment, siibra explorer node can only handle siibra-api running on port 10081 {sapi_tasks[0].port}. TODO fix in future"
        return True

    def pre(self):
        
        def process_sxplr_env(line: str):
            return line.lstrip().lstrip("/") if "endpoint-local-10081" in line else f"// {line}"
        
        # TODO not perfect, figure out a more permanent solution?
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
        sxplr_process = subprocess.Popen(["./node_modules/.bin/ng",
                                          "serve",
                                          "--port", str(self.port)], cwd=self.sxplr_path, start_new_session=True, stdout=log(f"{NAME_SPACE}-siibra-explorer.log"), stderr=subprocess.STDOUT)
        def kill_npm_process():
            sxplr_process.send_signal(signal.SIGTERM)
        self.cleanup_cb.append(kill_npm_process)

class SxplrDockerTask(PortedTask):
    name="sxplr_docker_task"
    DOCKER_TAG = "docker-registry.ebrains.eu/siibra/siibra-explorer:master"
    SXPLR_DOCKER_CONTAINER_NAME = "sxplr-container"
    
    def __init__(self, *args, port=8080, **kwargs) -> None:
        super().__init__(*args, port=port, **kwargs)
        self.sapi_port = None
    
    def should_run(self, workflow: Workflow) -> bool:
        sapi_tasks = workflow.find_tasks(SapiTask)
        assert len(sapi_tasks) == 1, f"Expected one and only one siibra-api task to be run, but got {len(sapi_tasks)}"
        self.sapi_port = sapi_tasks[0].port
        return True

    def pre(self):
        subprocess.run(["docker", "pull", self.DOCKER_TAG], stdout=log(f"{NAME_SPACE}-siibra-explorer-pull.log"), stderr=subprocess.STDOUT)
    
    def run(self):
        
        subprocess.run(["docker", "run",
                        "-p", f"127.0.0.1:{self.port}:8080",
                        "--name", self.SXPLR_DOCKER_CONTAINER_NAME,
                        "--rm",
                        "-dit",
                        "--env", f"OVERWRITE_API_ENDPOINT=http://localhost:{self.sapi_port}/v3_0",
                        self.DOCKER_TAG],
                        stdout=log(f"{NAME_SPACE}-siibra-explorer.log"),
                        stderr=subprocess.STDOUT)
        def terminate_docker():
            subprocess.run(["docker", "stop", self.SXPLR_DOCKER_CONTAINER_NAME])
        self.cleanup_cb.append(terminate_docker)
