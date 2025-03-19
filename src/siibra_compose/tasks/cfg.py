from siibra_compose.util import Task, get_module_path, get_latest_siibra_version
from siibra_compose.const import CONFIG_PATH_KEY
from siibra_compose.util import PortedTask, get_module_path, log, get_latest_release, Workflow, logger, Status, verify_port
from .spy import SpyTask

class ConfigTask(Task):
    name="config_task"
    
    def __init__(self, config, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config=config

    def should_run(self, workflow: Workflow):
        if self.config:
            return True
        
        spy_tasks = [ task for task in workflow.find_tasks(SpyTask) ]
        assert len(spy_tasks) == 1, f"Expecting one and only one spy_task, but got {len(spy_tasks)}"
        spy_installed = (spy_tasks[0].status == Status.SUCCESS)
        if not spy_installed:
            return False
        assert spy_installed, f"siibra-python must be installed first."

        siibra_version = spy_tasks[0].version
        siibra_version = siibra_version.lstrip("v")
        self.config = f"siibra-{siibra_version}"
        return True

    def pre(self, *args, **kwargs):
        config = self.config or f"siibra-{get_latest_siibra_version()}"
        github_repo = "https://github.com/FZJ-INM1-BDA/siibra-configurations.git"
        jugit_repo = "https://jugit.fz-juelich.de/t.dickscheid/brainscapes-configurations.git"
        config_repo = jugit_repo if config.startswith("siibra-0.4") else github_repo
        config_path=get_module_path(config, config_repo)
        self.keyval[CONFIG_PATH_KEY]=config_path
