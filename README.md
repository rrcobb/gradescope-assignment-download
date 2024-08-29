# Gradescope PDF Assignment Download

Downloads all your gradescope assignments as pdfs.

Based on https://github.com/mooey5775/gradescope.

Note: totally skips your programming assignments. If you use that feature, hopefully you store those assignments in another place and don't need to download them.

## What it does: download files for assignments

- web-scrapes Gradescope
- downloads content
- formats content into files in a target folder

## Run it

```sh
uv install
uv run main.py
```

The `config.yaml` file should contain your Gradescope credentials.

```yaml
# credentials for https://gradescope.com
gradescope:
  username: ""
  password: ""
```

Set the target directory in `main.py` -- the `TARGET_DIR` constant. The script will fail if the dir doesn't exist, so be sure to mkdir it first.

The script takes a while to run, but it's also resumable -- you can kill it, and it will skip files it's already downloaded. That also means you can fix issues in the JSON (see below) and then re-run it safely, without needing to re-download all the pdfs.

## About

Most of the annoying part of webscraping gradescope is dealing with the cookies so you can make authenticated requests.

That's all wrapped up here into the gradescope/ folder, so you can set your config, then use `gradescope.api.request` to fetch gradescope pages as yourself. See `gradescope/macros.py`

The next grunge-work part is reading the response content and dealing with it, which is time-consuming, but not all that hard. Most gradescope responses have the data you want in the html; sometimes it's in a data-attr.

The other somewhat annoying thing is writing to pdf. We use the fpdf2 library, and some free fonts. Getting the formatting right takes some trial and error.
