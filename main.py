import click
import subprocess
from pathlib import Path
from tempfile import mkdtemp
import os
from time import sleep
import signal
import shutil
import requests

NAME_SPACE="siibra-violet"

def get_module_path(arg, git_url):
    if Path(arg).is_dir():
        module_path = arg
        used_tmp = False
    else:
        module_path = mkdtemp()
        subprocess.run(["git", "clone", "--depth", "1", "-b", arg, git_url, module_path])
        used_tmp = True
    def callback():
        if not used_tmp:
            return
        shutil.rmtree(module_path, ignore_errors=True)
    return module_path, callback

def get_latest_release(owner: str, repo: str):

    resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}/releases")
    resp.raise_for_status()
    releases = resp.json()
    assert len(releases) > 0
    return releases[0]

@click.command()
@click.option("--config", help="Path to local config, or commit'ish on main repo. Default to latest release.")
@click.option("--spy", help="Path to local siibra-python repo, or version tag, or commit'ish on main repo. Default to latest release.")
@click.option("--sapi", help="Path to local siibra-api, or version tag, or commit'ish on main repo. Default to latest release.")
@click.option("--sxplr", help="Path to local siibra-explorer, or version tag, or commit'ish on main repo. Default to latest release.")
@click.option("--clean", help="Clean install", default=False)
def main(config, spy, sapi, sxplr, clean):
    
    latest_version = None
    if config is None or spy is None:
        latest_release = get_latest_release("fzj-inm1-bda", "siibra-python")
        latest_tag: str = latest_release.get("tag_name")
        assert latest_tag
        latest_version = latest_tag.lstrip("v")

    cleanup_callbacks = []

    def cleanup():
        # in the event that more items gets appended to cleanup_callback while it is been iterated over.
        while len(cleanup_callbacks) > 0:
            cb = cleanup_callbacks.pop()
            try:
                cb()
            except Exception as e:
                print("callback called unsuccessfully")
                print(e)

    config_path, config_callback = get_module_path(config or f"siibra-{latest_version}", "https://jugit.fz-juelich.de/t.dickscheid/brainscapes-configurations.git")
    cleanup_callbacks.append(config_callback)
    
    spy_path, spy_callback = get_module_path(spy or f"v{latest_version}", "https://github.com/FZJ-INM1-BDA/siibra-python.git")
    cleanup_callbacks.append(spy_callback)

    latest_sapi = None
    if sapi is None:
        latest_sapi_release = get_latest_release("fzj-inm1-bda", "siibra-api")
        latest_sapi = latest_sapi_release.get("tag_name")
        
    sapi_path, sapi_callback = get_module_path(sapi or latest_sapi, "https://github.com/fzj-inm1-bda/siibra-api.git")
    cleanup_callbacks.append(sapi_callback)


    if sxplr is not None:
        sxplr_path, sxplr_callback = get_module_path(sxplr, "https://github.com/fzj-inm1-bda/siibra-explorer.git")
        cleanup_callbacks.append(sxplr_callback)

    def log(filename):
        fp = open(filename, "a")
        cleanup_callbacks.append(lambda: fp.close())
        return fp
    
    try:
        if clean:
            print("clean flag set, uninstall siibra")
            subprocess.run(["pip", "uninstall", "-y", "siibra"], stdout=log(f"{NAME_SPACE}-siibra-python.log"), stderr=subprocess.STDOUT)
        
        print("installing siibra-python")
        subprocess.run(["pip", "install", "-e", spy_path], stdout=log(f"{NAME_SPACE}-siibra-python.log"), stderr=subprocess.STDOUT)
        print("installing siibra-api")
        subprocess.run(["pip", "install", "-r", Path(sapi_path) / "requirements" / "all.txt" ], stdout=log(f"{NAME_SPACE}-siibra-api.log"), stderr=subprocess.STDOUT)

        print("pulling redis")
        subprocess.run(["docker", "pull", "redis"], stdout=log(f"{NAME_SPACE}-redis-pull.log"), stderr=subprocess.STDOUT)

        print("starting redis container")
        subprocess.Popen(["docker", "run",
                        "-it",
                        "-p", "127.0.0.1:6379:6379",
                        "--rm",
                        "--name", f"{NAME_SPACE}-redis",
                        "redis"], stdout=log(f"{NAME_SPACE}-redis.log"), stderr=subprocess.STDOUT)
        cleanup_callbacks.append(lambda: subprocess.run([ "docker", "stop", f"{NAME_SPACE}-redis" ], stdout=log(f"{NAME_SPACE}-redis.log"), stderr=subprocess.STDOUT))

        api_process = subprocess.Popen(["uvicorn", "api.server:api", "--port", "10081"], cwd=sapi_path, start_new_session=True, env={
            **os.environ,
            "SIIBRA_USE_CONFIGURATION": config_path,
        }, stdout=log(f"{NAME_SPACE}-siibra-api.log"), stderr=subprocess.STDOUT)
        cleanup_callbacks.append(lambda: api_process.send_signal(signal.SIGTERM))


        if sxplr is not None:
            def process_sxplr_env(line: str):
                return line.lstrip().lstrip("/") if "endpoint-local-10081" in line else f"// {line}"
            
            path_to_env = Path(sxplr_path, "src/environments/environment.common.ts")
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
            cleanup_callbacks.append(spxlr_env_cleanup)
            
            print("installing siibra-explorer dependencies")
            subprocess.run(["npm", "i"], cwd=sxplr_path, stdout=log(f"{NAME_SPACE}-siibra-explorer-install.log"), stderr=subprocess.STDOUT)

            print("running dev siibra-explorer")
            sxplr_process = subprocess.Popen(["./node_modules/.bin/ng", "serve"], cwd=sxplr_path, start_new_session=True, stdout=log(f"{NAME_SPACE}-siibra-explorer.log"), stderr=subprocess.STDOUT)
            def kill_npm_process():
                sxplr_process.send_signal(signal.SIGTERM)
            cleanup_callbacks.append(kill_npm_process)
        else:
            print("siibra-explorer tag not defined. Using docker-registry.ebrains.eu/siibra/siibra-explorer:master-local-10081")
            DOCKER_TAG = "docker-registry.ebrains.eu/siibra/siibra-explorer:master-local-10081"
            SXPLR_DOCKER_CONTAINER_NAME = "sxplr-container"
            subprocess.run(["docker", "pull", DOCKER_TAG], stdout=log(f"{NAME_SPACE}-siibra-explorer-pull.log"), stderr=subprocess.STDOUT)
            subprocess.run(["docker", "run",
                            "-p", "127.0.0.1:8080:8080",
                            "--name", SXPLR_DOCKER_CONTAINER_NAME,
                            "--rm",
                            "-dit",
                            DOCKER_TAG],
                            stdout=log(f"{NAME_SPACE}-siibra-explorer.log"),
                            stderr=subprocess.STDOUT)
            def terminate_docker():
                subprocess.run(["docker", "stop", SXPLR_DOCKER_CONTAINER_NAME])
            cleanup_callbacks.append(terminate_docker)
            
        sleep(10)
        print("siibra-explorer should be ready on http://localhost:8080/")

    except Exception as e:
        print("Error in startup script, terminating...")
        print(e)
        cleanup()
        raise
    
    except KeyboardInterrupt as e:
        print("Interrupted by user, terminating ...")
        cleanup()
        raise
    
    while True:
        try:
            sleep(5)
        except KeyboardInterrupt:
            print("Interrupted by user, terminating ...")
            cleanup()
            break


if __name__ == "__main__":
    main()