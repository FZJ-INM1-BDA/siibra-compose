# siibra-compose

Similar to `docker-compose`, siibra-compose is designed to be a one stop shop for spinning up a working environment of siibra-toolsuite.

One command to:

- start [siibra-api](https://github.com/fzj-inm1-bda/siibra-api/) (local directory or remote commit'ish) with
- [siibra-python](https://github.com/fzj-inm1-bda/siibra-python/) (local directory or remote commit'ish) using
- [siibra-configurations](https://github.com/FZJ-INM1-BDA/siibra-configurations/) (local directory or remote commit'ish) visualized with
- [siibra-explorer](https://github.com/fzj-inm1-bda/siibra-explorer/) (local directory or remote commit'ish)

## Requirements

Python `venv` and ...

| service name | commit'ish | local directory | empty | + common |
| --- | --- | --- | --- | --- |
| siibra-config | git | | git | |
| siibra-python | git | | git | python3.7+ |
| siibra-api | git |  | git | python3.7+,(docker if redis is enabled) |
| siibra-explorer | git, node14+ | node14+ | docker |

## Installation

```sh

$ pip install git+https://github.com/FZJ-INM1-BDA/siibra-compose.git

```

## Example Usages

### Hello World

Example below shows a minimal working example. It will use the latest released siibra-configurations, siibra-python, siibra-api and siibra-explorer.

```sh
# create a new venv, activate it
$ echo '{"version": "0.0.1"}' > siibra-compose.json
$ siibra-compose
```

### Without docker

If you do not have docker installed on your system, you can forgo redis cache, and run siibra-explorer locally:

```sh

$ echo '{
    "$schema": "https://raw.githubusercontent.com/FZJ-INM1-BDA/siibra-compose/refs/heads/master/siibra-compose-schema.json",
    "version": "0.0.1",
    "explorer": {
        "port": 7700,
        "ref": "master"
    },
    "api": {
        "redis": {
            "disabled": true
        },
        "ref": "master"
    },
    "python": {
        "ref": "v0.4a87"
    },
    "config": {
        "ref": "siibra-0.4a87"
    }
}' > siibra-compose.json
$ siibra-compose
```

### Complex Usecase

Example below shows a more complex usecase. It uses siibra-configuration from a local directory `/path/to/my/siibra-config`, siibra-python from the remote branch `branch-to-checkout`, siibra-api from the tag `tag-to-checkout` and latest production version of siibra-explorer. 

Additionally, siibra-api is configured to run on port `7095`, with the redis caching turned off, and siibra-explorer is configured to run on port `10001`. 

Lastly, it also shows the JSONSchema file in the repository `./siibra-compose-schema.json`, which hopefully would help one write configuration JSON much easily.

```sh
$ echo '{
    "$schema": "https://raw.githubusercontent.com/FZJ-INM1-BDA/siibra-compose/refs/heads/master/siibra-compose-schema.json",
    "version": "0.0.1",
    "config": {
        "ref": "/path/to/my/siibra-config"
    },
    "python": {
        "ref": "branch-to-checkout"
    },
    "api": {
        "ref": "tag-to-checkout",
        "port": 7095,
        "redis": {
            "disabled": true
        }
    },
    "explorer": {
        "port": 10001
    }
}' > complex-siibra-compose.json
$ siibra-compose -f complex-siibra-compose.json
```

## License

MIT
