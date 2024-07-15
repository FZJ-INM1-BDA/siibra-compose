from util import Workflow, get_latest_release
import click
from siibra_compose.logger import logger

from .tasks import ConfigTask, SpyTask, SapiTask, SxplrNodeTask, SxplrDockerTask


@click.command()
@click.option("--config", help="Path to local config, or commit'ish on main repo. Default to latest release.")
@click.option("--spy", help="Path to local siibra-python repo, or version tag, or commit'ish on main repo. Default to latest release.")
@click.option("--sapi", help="Path to local siibra-api, or version tag, or commit'ish on main repo. Default to latest release.")
@click.option("--sxplr", help="Path to local siibra-explorer, or version tag, or commit'ish on main repo. Default to latest release.")
@click.option("--debug", help="Show debug logs", default=False)
def main(config, spy, sapi, sxplr, debug):

    if debug:
        logger.setLevel("DEBUG")
    
    workflow=Workflow()
    
    config_task=ConfigTask(config)
    workflow.register_task(config_task)
    
    spy_task = SpyTask(spy, )
    workflow.register_task(spy_task)

    sapi_task = SapiTask(sapi, )
    workflow.register_task(sapi_task)

    sxplr_task = SxplrNodeTask(sxplr) if sxplr else SxplrDockerTask()
    workflow.register_task(sxplr_task)

    workflow.run()

if __name__ == "__main__":
    main()
