from siibra_compose.util import Task, get_module_path, get_latest_siibra_version
from siibra_compose.const import CONFIG_PATH_KEY

class ConfigTask(Task):
    name="config_task"
    
    def __init__(self, config, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config=config

    def pre(self, *args, **kwargs):
        config_path=get_module_path(self.config or f"siibra-{get_latest_siibra_version()}", "https://github.com/FZJ-INM1-BDA/siibra-configurations.git")
        self.keyval[CONFIG_PATH_KEY]=config_path
