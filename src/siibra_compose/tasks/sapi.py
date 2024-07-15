import subprocess
from pathlib import Path
import signal
import os

from siibra_compose.util import PortedTask, get_module_path, log, get_latest_release, Workflow, logger, Status, verify_port
from siibra_compose.const import NAME_SPACE, CONFIG_PATH_KEY
from .spy import SpyTask

class SapiTask(PortedTask):
    name="sapi_task"

    def __init__(self, sapi: str, *args, redis=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if redis is None:
            redis = {
                "port": 6379,
                "disabled": False
            }
        self.sapi=sapi
        self.cleanup_api=None
        self.sapi_path: str=None
        self.redis_disabled = redis.get("disabled", False)
        self.redis_port = redis.get("port", 6379)
    
    def __post_init__(self):
        super().__post_init__()
        verify_port(self.redis_port)
    
    
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
        
        spy_tasks = [ task for task in workflow.get_tasks(SpyTask) ]
        assert len(spy_tasks) == 1, f"Expecting one and only one spy_task, but got {len(spy_tasks)}"
        spy_installed = (spy_tasks[0].status == Status.SUCCESS)
        logger.debug(f"{self.name} should run: {config_cloned and spy_installed}")
        return config_cloned and spy_installed
    
    def run(self):
        subprocess.run(["pip", "install", "-r", Path(self.sapi_path) / "requirements" / "all.txt" ], stdout=log(f"{NAME_SPACE}-siibra-api.log"), stderr=subprocess.STDOUT)
        if not self.redis_disabled:
            subprocess.run(["docker", "pull", "redis"], stdout=log(f"{NAME_SPACE}-redis-pull.log"), stderr=subprocess.STDOUT)
    
        # First, start redis instance, 
        if not self.redis_disabled:
            subprocess.Popen(["docker", "run",
                            "-it",
                            "-p", f"localhost:{self.redis_port}:6379",
                            "--rm",
                            "--name", f"{NAME_SPACE}-redis",
                            "redis"],
                            stdout=log(f"{NAME_SPACE}-redis.log"),
                            stderr=subprocess.STDOUT)
            self.cleanup_cb.append(lambda: subprocess.run([ "docker", "stop", f"{NAME_SPACE}-redis" ], stdout=log(f"{NAME_SPACE}-redis.log"), stderr=subprocess.STDOUT))

        # Now, start the uvicorn instance
        api_process=subprocess.Popen(["uvicorn", "api.server:api", "--port", f"{self.port}"], cwd=self.sapi_path, start_new_session=True, env={
            **os.environ,
            "SIIBRA_USE_CONFIGURATION": self.keyval[CONFIG_PATH_KEY],
            "REDIS_PORT": str(self.redis_port)
        }, stdout=log(f"{NAME_SPACE}-siibra-api.log"), stderr=subprocess.STDOUT)
        self.cleanup_cb.append(lambda: api_process.send_signal(signal.SIGTERM))
