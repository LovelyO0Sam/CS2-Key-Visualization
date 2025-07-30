# CS2-Key-Visualization

A Python script to generate keystroke and mouse-click overlay videos from Counter-Strike 2 demo files.

![Example Keyboard Overlay](https://raw.githubusercontent.com/LovelyO0Sam/CS2-Key-Visualization/refs/heads/main/images/ropz.png)  
---

## Features

- Uses game state properties (`is_walking`, `duck_amount`, `velocity_Z`) for accurate detection of walking, crouching, and jump events.
- Generates a single MP4 video file containing keyboard and mouse inputs.
- Supports two analysis modes: by round (`--rounds`) or by a specific tick range (`--ticks`).
- Resamples demo tick data to a standard 60 FPS video to ensure the output duration matches the gameplay time.

---

## Prerequisites

1.  **Python 3.8+**
2.  **FFmpeg:** This external dependency is required for video encoding.
    - **Windows:** Download a build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or [BtbN](https://github.com/BtbN/FFmpeg-Builds/releases). Add the `bin` folder to your system's PATH.
    - **macOS:** `brew install ffmpeg`
    - **Linux:** `sudo apt-get install ffmpeg` (Debian/Ubuntu)

---

## Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/LovelyO0Sam/CS2-Key-Visualization
    cd CS2-Key-Visualization
    ```

2.  **Install Python packages:**
    ```sh
    pip install -r requirements.txt
    ```

---

## Usage

The script is run from the command line with the following structure:

```sh
python key-visualization.py <demo_path> <player_name> <output_base_path> [options]
```

### Finding a Player's Name

If you are unsure of a player's exact, case-sensitive name, use `list` as the player name. This will print all available player names from the demo file and exit. The `output_base_path` argument is still required but will not be used.

```sh
python key-visualization.py "C:\cs2_demos\example.dem" list "dummy_path"
```

### Arguments

- `demo_path`: Full path to the `.dem` file.
- `player_name`: The exact, case-sensitive in-game name of the player, or `list` to see all available player names.
- `output_base_path`: The base path and name for the output video file (e.g., `C:\videos\my_clip`).
- `[options]`: See below.

### Options

| Option           | Description                                                                                             | Default   |
| ---------------- | ------------------------------------------------------------------------------------------------------- | --------- |
| `-h`, `--help`   | Show the help message and exit.                                                                         |           |
| `-r`, `--rounds` | Comma-separated list of round numbers (e.g., '1,5,16'). Use 'all' for all rounds.                       | 'all'     |
| `--ticks`        | A specific tick range to process (e.g., '5000,15000'). Cannot be used with `--rounds`.                   | None      |
| `--tickrate`     | The tickrate of the demo file. Crucial for accurate video duration.                                     | 64        |
| `--ffmpeg-codec` | The FFmpeg video codec for the final output.                                                            | 'libx264' |
| `-p`, `--processes`| Number of CPU processes to use (only affects round-based mode).                                         | All cores |

### Examples

**Generate video for all rounds (assumes 64-tick):**
```sh
python key-visualization.py "C:\cs2_demos\mydemo.dem" "Player1" "C:\outputs\Player1_analysis"
```

**Generate video for rounds 2 and 16 of a 64-tick demo:**
```sh
python key-visualization.py "demos/faceit.dem" "s1mple" "vids/s1mple_clutch" -r "2,16" --tickrate 64
```

**Generate a video for a specific tick range:**
```sh
python key-visualization.py "demos/premier.dem" "ZywOo" "vids/ZywOo_ace" --ticks "85000,95000"
```

---

## Dependencies & Licensing

This project uses the following open-source libraries:

- **[demoparser2](https://github.com/LaihoE/demoparser):** (MIT License)
- **[Pandas](https://pandas.pydata.org/):** (BSD 3-Clause License)
- **[NumPy](https://numpy.org/):** (BSD 3-Clause License)
- **[OpenCV-Python](https://pypi.org/project/opencv-python/):** (MIT License)

This script requires a separate installation of **FFmpeg**, which is available under various licenses (e.g., LGPL, GPL). This project does not distribute FFmpeg. You are responsible for acquiring it and complying with its license.

## Project License

This project is licensed under the MIT License. See the `LICENSE` file for details.
