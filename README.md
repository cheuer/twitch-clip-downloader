# Twitch Clip Downloader

## Running from source

- Install Python 3.10+
- Install requirements in `requirements.txt`. It's recommended to do this in a virtual env:
    ```bash
    py -m venv --copies .venv
    .venv\\Scripts\\activate.bat
    python.exe -m pip install -r requirements.txt
    ```
- Copy/rename `example.env` to `.env` and replace the example IDs with proper values from your own Twitch API app
- Run the script
    ```bash
    .venv\\scripts\\activate.bat
    python ./twitch-clip-downloader.py
    ```
