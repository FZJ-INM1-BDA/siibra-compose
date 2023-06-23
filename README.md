# siibra violet (name pending)

One command to:

- start siibra-api (local directory or remote commit'ish) with
- siibra-python (local directory or remote commit'ish) using
- siibra-configuration (local directory or remote commit'ish) visualized with
- siibra-explorer (local directory or remote commit'ish)

## requirements

python3.7+
node14+
docker

## example

```sh

# create a new venv, activate it
python -m venv venv/ && . venv/bin/activate && pip install -U pip

python main.py \

    # use siibra configuration commitish feat_addJba3ColinMesh from remote
    --config feat_addJba3ColinMesh \ 

    # use siibra-python commit'ish (tag) v0.4a57
    --spy v0.4a57 \ 

    # use siibra-api from local directory
    --sapi ~/dev/projects/siibra-api/ \

    # use siibra-explorer from local directory
    --sxplr ~/dev/projects/siibra-explorer/
```

## TODO

If not supplied, use latest/stable. In some cases, node14+ requirement can also be dropped.