# YouTube Analytics Automation

This repository provides a Python script that automates downloading the current
view from the YouTube Studio analytics dashboard for a specific video. The
automation is built with Selenium and reuses an existing Chrome profile so that
no credentials are stored in the project.

## Prerequisites

* Python 3.9 or newer
* Google Chrome
* ChromeDriver that matches the installed Chrome version
* The Chrome profile already logged in to the YouTube channel that owns the
  target video

Install the Python dependencies::

    pip install -r requirements.txt

## Usage

1. Determine the local Chrome user data directory that contains the desired
   Google account. Common locations are:
   * **Windows:** `C:\\Users\\<you>\\AppData\\Local\\Google\\Chrome\\User Data`
   * **macOS:** `~/Library/Application Support/Google/Chrome`
   * **Linux:** `~/.config/google-chrome`
2. (Optional) Identify the profile directory name (for example `Profile 1` or
   `Default`).
3. Create a directory where the exported CSV files should be saved.
4. Run the automation script:

```bash
python scripts/youtube_analytics_downloader.py \
    --video-url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
    --user-data-dir "~/Library/Application Support/Google/Chrome" \
    --profile-directory "Profile 1" \
    --download-dir ~/Downloads/youtube-analytics \
    --chrome-driver-path /path/to/chromedriver
```

### Arguments

* `--video-url` – Full YouTube watch URL of the video whose analytics you want to
  export.
* `--user-data-dir` – Path to the Chrome user data directory that contains the
  authenticated account.
* `--profile-directory` – Optional profile folder inside the user data directory
  (omit it to use the default profile).
* `--download-dir` – Destination directory for the CSV export. The directory is
  created automatically when it does not exist.
* `--chrome-driver-path` – Optional path to the ChromeDriver executable. If not
  provided, Selenium will look for one on your `PATH`.
* `--chrome-binary-path` – Optional path to the Chrome executable.
* `--wait-after-download` – Seconds to wait after triggering the export to give
  Chrome time to finish the download (defaults to 5 seconds).

## What the script does

* Launches Chrome with the requested profile.
* Opens the YouTube Studio analytics page for the provided video.
* Switches to the advanced analytics view.
* Triggers the "Export current view" action and selects the CSV format.

> **Note:** You must complete any required two-factor authentication manually in
> the browser window the first time you run the script.

