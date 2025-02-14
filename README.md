# Video Merger Script

## First time executing script

1. Install dependencies for downloading and merging videos, to do this I used Brew (See https://brew.sh/ on instructions on how to install it).

```bash
brew install ffmpeg
```

2. Generate python virtual environment

```bash
python3 -m venv env
```

3. Activate python virtual environment

```bash
source ./env/bin/activate
```

4. Install python dependencies to run script

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Locate a xlsx file containing the files info in the current folder, this file should be named data.xlsx

6. Run script

```bash
python merge.py
```
