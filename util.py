from dataclasses import dataclass, field
from typing import List, Callable, Mapping
from enum import Enum
import requests
from pathlib import Path
from tempfile import mkdtemp
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from itertools import repeat
from logger import logger

class Status(Enum):
    PENDING='PENDING' # default signifies prior to run starting
    SUCCESS='SUCCESS' # set after run completes
    WARNING='WARNING' # set... during run/if run completes with error?
    ERROR='ERROR' # sets if run errors

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
    
    def __init__(self, *args, latest_version=None, **kwargs) -> None:
        if latest_version is None:
            raise RuntimeError(f"latest_version must be defined")
        self.latest_version = latest_version
        self.cleanup_cb: List[Callable] = []
    

    _CleanupCallbacks: List[Callable] = []
    @staticmethod
    def _Cleanup():
        while len(Task._CleanupCallbacks) > 0:
            Task._CleanupCallbacks.pop()()

@dataclass
class Workflow:
    tasks: List[Task] = field(default_factory=list)

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
                sleep(5)
                logger.info(f"\r{' | '.join([(task.name + ': ' + str(task.status)) for task in self.tasks])}")
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
        if not used_tmp:
            return
        shutil.rmtree(module_path, ignore_errors=True)
    Task._CleanupCallbacks.append(callback)
    return module_path

def log(filename):
    fp = open(filename, "a")
    Task._CleanupCallbacks.append(fp.close)
    return fp
