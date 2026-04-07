# Codex Anamnestia

Holoearth Wiki management suite.

## Install

1. Clone from GitHub

2. Install python

3. Install dependencies

Run `pip install -r requirements.txt`.

4. Add Credentials to .env

Set `WIKI_USERNAME` and `WIKI_PASSWORD`.

## Usage

### Update & Upload
1. 

Edit `src/generators/templates/meta.json` version number.

2.

Run `py main.py --all-specs --action full --version VERSION_NUMBER_HERE`

### Flags

- `--spec`: Use a specific specification file name (e.g. `item_spec`).
- `--all-specs`: Run the specified action for all spec files in `configs/specs`.
- `--action`: The action to perform.
    - `collect`: Extraction only.
    - `resolve`: Extraction & resolution (saves to `staging/outputs`).
    - `generate-modules`: Resolution & Module generation (Lua/JSON maps).
    - `upload`: Upload staged files to the wiki.
    - `full` (default): Run all stages including archival and changelog.
    - `historical-update`: Special mode for backfilling data (requires `--version`).
    - `changelog`: Dedicated changelog generation.
- `--upload-target`: Specify what to upload.
    - `all` (default): Data, Modules, Templates, and Maps.
    - `data`: Resolved JSON/Lua data files.
    - `modules`: Lua modules (`Module:Data/...`).
    - `templates`: Wikitext templates (`Template:...`).
    - `maps`: JSON maps for interactive features.
- `--version`: The version string for the current run (e.g., `1.4.0.2`).
- `--force-upload`: Bypass the safety check if the version is NOT newer than the online version.
- `--verbose`: Enable debug-level logging.

### Changelog Flags
- `--changelog`: Generate a changelog against the previous archive.
- `--changelog-historical`: Compare current state against `configs/historical_update_config.yaml`.
- `--changelog-v1`: Manually specify the first comparison source (ZIP or directory).
- `--changelog-v2`: Manually specify the second comparison source (ZIP or directory).
