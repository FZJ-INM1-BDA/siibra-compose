import subprocess

from siibra_compose.util import Task, get_module_path, log, get_latest_siibra_version
from siibra_compose.const import NAME_SPACE

class SpyTask(Task):
    name="spy_task"

    def __init__(self, spy, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.spy=spy
    
    def pre(self):
        super().pre()
        spy_path = get_module_path(self.spy or f"v{get_latest_siibra_version()}", "https://github.com/FZJ-INM1-BDA/siibra-python.git")
        self.spy_path = spy_path
    
    def run(self):
        subprocess.run(["pip", "install", "-e", self.spy_path], stdout=log(f"{NAME_SPACE}-siibra-python.log"), stderr=subprocess.STDOUT)

    @property
    def version(self):
        return subprocess.check_output(["python", "-c", "import siibra; print(siibra.__version__)"]).decode().strip()
