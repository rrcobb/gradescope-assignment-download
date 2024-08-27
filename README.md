# Gradescope Scripts

Cloned gradescope folder from https://github.com/mooey5775/gradescope.

Then added scripts (main.py) for taking some gradescope actions.

## What it does: download files for assignments

The script basically web-scrapes Gradescope, downloads content, and then names files the way they need to be named.

## Configuration

The `config.yaml` file contains Gradescope credentials.

```yaml
gradescope:
  username: "" # credentials for https://gradescope.com
  password: ""
```

Set the target directory in `main.py` -- the `TARGET_DIR` constant. The script will fail if the dir doesn't exist.

## Set what to download

- course list
- see all assignments

## Install dependencies

```
pipenv shell
```
to start the venv


```
pipenv install
```

## Run

```sh
python main.py
```

or just `./main.py`


The script takes a while to run, but it's also resumable -- you can kill it, and it will skip files it's already downloaded. That also means you can fix issues in the JSON (see below) and then re-run it safely, without needing to re-download all the pdfs.
