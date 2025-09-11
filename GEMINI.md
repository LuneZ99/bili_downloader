# GEMINI.md

## Project Overview

This project is a command-line tool for downloading videos and dynamics (social media posts) from the Chinese video-sharing website Bilibili. It is written in Python and utilizes the `bilibili-api-python` library to interact with the Bilibili API.

The tool supports various features, including:
- Downloading single videos, all videos from a user, and video collections (series/seasons).
- Fetching user dynamics, including comments.
- Concurrent downloads using `asyncio` for better performance.
- Automatic video quality selection, with support for high-quality formats for authenticated users.
- Requires `ffmpeg` for merging video and audio streams.

The codebase is structured into several modules:
- `bili_cli.py`: The main entry point for the command-line interface, handling argument parsing and command dispatching.
- `video.py`: Contains the core logic for video downloading, including fetching video information, handling different stream types (FLV, MP4, DASH), and managing `ffmpeg` processes.
- `dynamic.py`: Implements the functionality for fetching and saving user dynamics and their comments.
- `utils.py`: Provides shared utility functions, primarily for setting up a unified logging system.
- `credentials.json.example`: An example file for configuring user credentials to access higher quality video streams.

## Building and Running

### 1. Installation

First, install the necessary Python dependencies:

```bash
pip install -r requirements.txt
```

This project also requires `ffmpeg` to be installed on the system for video and audio stream processing.

### 2. Configuration

To download high-quality videos, you need to provide your Bilibili login credentials. Copy the example configuration file:

```bash
cp credentials.json.example credentials.json
```

Then, edit `credentials.json` with your `SESSDATA`, `bili_jct`, `buvid3`, and `DedeUserID` values, which can be obtained from your browser's cookies after logging into bilibili.com.

### 3. Running the Tool

The tool is run from the command line using `bili_cli.py`. You can see the full list of commands and options by running:

```bash
python bili_cli.py --help
```

Here are some common commands:

- **List all videos from a user:**
  ```bash
  python bili_cli.py list-videos <USER_ID>
  ```

- **Download a single video:**
  ```bash
  python bili_cli.py download-video <BVID>
  ```

- **Download all videos from a user with 5 concurrent downloads:**
  ```bash
  python bili_cli.py download-user <USER_ID> --concurrent 5
  ```

- **Download all dynamics from a user:**
  ```bash
  python bili_cli.py download-dynamics <USER_ID>
  ```

## Development Conventions

- The project uses `asyncio` for all I/O-bound operations, such as API requests and file downloads.
- A centralized logging setup is provided in `utils.py` and used throughout the application.
- The code is organized into classes (`VideoDownloader`, `BilibiliVideoManager`, `DynamicsCrawler`, `BilibiliDynamicManager`) to encapsulate related functionality.
- Command-line argument parsing is handled by the `argparse` module in `bili_cli.py`.
- The `bilibili-api-python` library is the primary interface to the Bilibili API.
