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
    `py main.py --all-specs --action full --version VERSION_NUMBER_HERE`

### Flags

**--spec**

type=str, help='The name of the specification file to run.'

**--all-specs**

action='store_true', help='Run the specified action for all spec files.'

**--action**

type=str, choices=['collect', 'resolve', 'generate-modules', 'upload', 'full'], default='full', help='The action to perform.'

**--upload-target**

type=str, choices=['data', 'modules', 'all'], default='all', help="Specify what to upload."

**--version**

type=str, help='A specific version string (e.g., game version) for the upload.'

**--verbose**

action='store_true', help='Enable verbose logging output.'
