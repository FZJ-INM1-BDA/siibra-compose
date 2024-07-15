import click
from pathlib import Path
import sys
import json

from siibra_compose.util import Workflow
from siibra_compose.tasks import ConfigTask, SpyTask, SapiTask, SxplrDockerTask, SxplrNodeTask

def eprint(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)


def parse_v1(config_json):
    scfg = config_json.get("config", {})
    spy = config_json.get("python", {})
    sapi = config_json.get("api", {})
    sxplr = config_json.get("explorer", {})

    workflow=Workflow()
    
    config_task=ConfigTask(scfg.pop("ref", None), **scfg)
    workflow.register_task(config_task)
    
    spy_task = SpyTask(spy.pop("ref", None), **spy)
    workflow.register_task(spy_task)

    sapi_task = SapiTask(sapi.pop("ref", None), **sapi)
    workflow.register_task(sapi_task)

    sxplr_task = SxplrNodeTask(sxplr.pop("ref", None), **sxplr) if sxplr.get("ref") else SxplrDockerTask(**sxplr)
    workflow.register_task(sxplr_task)

    workflow.run()

@click.command()
@click.option("-f", "--file", help="Path to config")
def cli(file=None):
    if file is None:
        file = "./siibra-compose.json"
    file = Path(file)
    if not file.exists():
        eprint(f"config path {str(file)} does not exist")
        sys.exit(1)

    with open(file, "r") as fp:
        try:
            config_json = json.load(fp=fp)
        except json.JSONDecodeError as e:
            eprint(f"config at {str(file)} is not valid json!")
            sys.exc_info(1)
        except Exception as e:
            eprint(f"parsing config at {str(file)} error!: {str(e)}")
            sys.exc_info(1)
    
    cfg_version = config_json.get("version")
    if cfg_version == "0.0.1":
        parse_v1(config_json)
    else:
        eprint(f"config version {cfg_version} not supported")
        sys.exit(1)
