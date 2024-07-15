from dataclasses import dataclass, field
from typing import List, Callable, Mapping, TypeVar, Type, Union
from enum import Enum
import requests
from pathlib import Path
from tempfile import mkdtemp
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from itertools import repeat
import datetime

from .logger import logger

class Status(Enum):
    PENDING='PENDING' # default signifies prior to run starting
    SUCCESS='SUCCESS' # set after run completes
    WARNING='WARNING' # set... during run/if run completes with error?
    ERROR='ERROR' # sets if run errors


LINE_UP = '\033[1A'
LINE_CLEAR = '\x1b[2K'

class Task:
    name: str = "base_task"
    workflow: 'Workflow'=None
    status: Status=Status.PENDING
    keyval: Mapping={}

    def pre(self):
        """
        Pre script. Method is called at the preparative phase, 
        and will always be carried out.
        """
        ...

    def should_run(self, workflow: 'Workflow') -> bool:
        """
        The main way for Tasks to do dependency checking.
        Since workflow is passed as the first positional argument,
        the tasks can decide when the `run` can/should be run.
        """
        return True


    def run(self):
        """
        Actual script. Will be run after:
        pre is run, should_run returns True
        """
        ...

    def post(self):
        """
        Will be run after: `run`
        """
        ...

    def cleanup(self):
        """
        Cleanup method, will be called on Interrupt/Termination
        """
        while len(self.cleanup_cb) > 0:
            try:
                self.cleanup_cb.pop()()
            except Exception as e:
                fh = log(f"{self.name}.log")
                fh.write(f"Error cleaning up: {str(e)}")
    
    def __init__(self, *args, **kwargs) -> None:
        self.cleanup_cb: List[Callable] = []
    

    _CleanupCallbacks: List[Callable] = []
    @staticmethod
    def _Cleanup():
        while len(Task._CleanupCallbacks) > 0:
            Task._CleanupCallbacks.pop()()

class PortedTask(Task):
    def __init__(self, *args, port=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.port = port
    
    def __post_init__(self):
        verify_port(self.port)


T = TypeVar("T", bound=Task)

@dataclass
class Workflow:
    tasks: List[Task] = field(default_factory=list)

    def find_tasks(self, TaskType: Type[T]):
        return [t for t in self.tasks if isinstance(t, TaskType)]


    @staticmethod
    def RunPre(task: Task):
        task.pre()
    
    @staticmethod
    def Run(task: Task, workflow: 'Workflow'):
        try:
            while not task.should_run(workflow):
                sleep(1)
            task.run()
            task.status = Status.SUCCESS
        except Exception as e:
            task.status = Status.ERROR
            logger.error(f"Running task failed: {str(e)}")
            
        
    @staticmethod
    def RunPost(task: Task):
        task.post()

    @staticmethod
    def Cleanup(task: Task):
        try:
            task.cleanup()
        except Exception as e:
            logger.warn(f"Cleanup failed! {str(e)}")

    def register_task(self, task: Task):
        self.tasks.append(task)
        task.workflow = self
    
    def cleanup(self):
        with ThreadPoolExecutor() as ex:
            ex.map(
                Workflow.Cleanup,
                self.tasks
            )
        Task._Cleanup()
    
    def run(self):
        try:
            logger.info(">>> starting...")
            with ThreadPoolExecutor() as ex:
                ex.map(
                    Workflow.RunPre,
                    self.tasks
                )
            logger.info(">>> Running...")
            with ThreadPoolExecutor() as ex:
                ex.map(
                    Workflow.Run,
                    self.tasks,
                    repeat(self)
                )
            logger.info(">>> PostRunning...")
            with ThreadPoolExecutor() as ex:
                ex.map(
                    Workflow.RunPost,
                    self.tasks
                )
        except Exception as e:
            logger.error(f"Error: {str(e)}! Terminating")
            self.cleanup()
        
        logger.info(f"Boot complete. Checking status ...")
        while True:
            try:
                t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                msg = f"{t} {' | '.join([(task.name + ': ' + str(task.status)) for task in self.tasks])}"
                print(msg)
                sleep(5)
                print(LINE_CLEAR, end=LINE_UP)
                
            except KeyboardInterrupt:
                logger.info(f"Interrupted by user, terminating ...")
                break

        self.cleanup()



def get_latest_release(owner: str, repo: str):

    resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}/releases")
    resp.raise_for_status()
    releases = resp.json()
    assert len(releases) > 0
    return releases[0]

def get_module_path(arg, git_url):
    """
    Get module path.
    
    If a path is provided
    - return the said path

    If a commitish is provided, will:
    - create tempdir
    - git clone and checkout the commitish
    - return tempdir
    """
    if Path(arg).is_dir():
        module_path = arg
        used_tmp = False
    else:
        module_path = mkdtemp()
        subprocess.run(["git", "clone", "--depth", "1", "-b", arg, git_url, module_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        used_tmp = True

    def callback():
        if used_tmp:
            shutil.rmtree(module_path, ignore_errors=True)
    Task._CleanupCallbacks.append(callback)
    return module_path

def log(filename):
    fp = open(filename, "a")
    Task._CleanupCallbacks.append(fp.close)
    return fp

def verify_port(port: Union[int, str]):
    if isinstance(port, int):
        return
    try:
        int(port)
    except ValueError as e:
        raise RuntimeError(f"Cannot parse {port} as int") from e

_cache_value = None
def get_latest_siibra_version():
    """Cache is used here, not only for efficiency, but also to prevent the rare scenario where between two separate calls to get_latest_siibra_version, a new release is made."""
    global _cache_value
    if _cache_value is None:
        latest_release=get_latest_release("fzj-inm1-bda", "siibra-python")
        latest_tag: str=latest_release.get("tag_name")
        assert latest_tag, f"Expected tag_name to be defined, but was not"
        _cache_value = latest_tag.lstrip("v")
    return _cache_value
