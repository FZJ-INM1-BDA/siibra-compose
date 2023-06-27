# siibra violet (name pending)

One command to:

- start siibra-api (local directory or remote commit'ish) with
- siibra-python (local directory or remote commit'ish) using
- siibra-configuration (local directory or remote commit'ish) visualized with
- siibra-explorer (local directory or remote commit'ish)

## requirements

| service name | commit'ish | local directory | empty | + common |
| --- | --- | --- | --- | --- |
| siibra-config | git | | git | |
| siibra-python | git | | git | python3.7+ |
| siibra-api | git |  | git | python3.7+,docker |
| siibra-explorer | git, node14+ | node14+ | docker |

empty ports on:

6379, 10081, 8080

## example

```sh

# create a new venv, activate it
python -m venv venv/ && . venv/bin/activate && pip install -U pip && pip install -r requirements.txt

python main.py \
    --config feat_addJba3ColinMesh `# use siibra configuration commitish feat_addJba3ColinMesh from remote` \
    --spy v0.4a57 `# use siibra-python commit'ish (tag) v0.4a57` \
    --sapi ~/dev/projects/siibra-api/ `# use siibra-api from local directory` \
    --sxplr ~/dev/projects/siibra-explorer/ `# use siibra-explorer from local directory`
```

## TODO

If not supplied, use latest/stable. In some cases, node14+ requirement can also be dropped.
