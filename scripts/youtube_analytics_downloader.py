"""Automate exporting YouTube Studio analytics for a specific video.

The script relies on Selenium and an existing Chrome profile that already has
access to the desired YouTube channel. It performs the following steps:

1. Launches Chrome using the requested profile (user data directory) so that the
   correct Google account is used.
2. Navigates to YouTube Studio and opens the analytics page for the video.
3. Switches to the advanced analytics view ("See more" / "Advanced mode").
4. Exports the current view as a CSV file.

Because the YouTube Studio UI changes regularly and may use different text for
various locales, the script looks for several alternative labels and falls back
on partial matches where possible. The selectors were chosen so that they rely
on stable accessibility labels instead of textual content rendered on screen.

Usage example::

    python scripts/youtube_analytics_downloader.py \
        --video-url "https://www.youtube.com/watch?v=VIDEO_ID" \
        --chrome-driver-path /path/to/chromedriver \
        --user-data-dir "$HOME/Library/Application Support/Google/Chrome" \
        --profile-directory "Profile 1" \
        --download-dir /tmp/downloads

"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import time
import urllib.parse
from typing import Iterable, Optional

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement as RemoteWebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Default timeout for waits (in seconds)
DEFAULT_TIMEOUT = 30


class AutomationError(RuntimeError):
    """Raised when a required element cannot be located or interacted with."""


def parse_video_id(video_url: str) -> str:
    """Extract the video ID from a YouTube video URL."""

    parsed = urllib.parse.urlparse(video_url)

    if parsed.netloc.endswith("youtu.be"):
        video_id = parsed.path.lstrip("/")
        if not video_id:
            raise ValueError(f"Could not extract video id from {video_url!r}")
        return video_id

    query = urllib.parse.parse_qs(parsed.query)
    if "v" in query:
        return query["v"][0]

    match = re.search(r"/embed/([a-zA-Z0-9_-]{11})", parsed.path)
    if match:
        return match.group(1)

    raise ValueError(f"Unsupported YouTube URL format: {video_url!r}")


def build_driver(
    *,
    chrome_driver_path: Optional[pathlib.Path],
    chrome_binary_path: Optional[pathlib.Path],
    user_data_dir: pathlib.Path,
    profile_directory: Optional[str],
    download_dir: pathlib.Path,
) -> WebDriver:
    """Create and configure a Selenium Chrome driver."""

    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_directory:
        options.add_argument(f"--profile-directory={profile_directory}")

    if chrome_binary_path:
        options.binary_location = str(chrome_binary_path)

    options.add_argument("--disable-popup-blocking")
    options.add_argument("--start-maximized")

    prefs = {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)

    service = Service(str(chrome_driver_path)) if chrome_driver_path else Service()
    return webdriver.Chrome(service=service, options=options)


def wait_for_any_label(
    driver: WebDriver,
    selectors: Iterable[str],
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[RemoteWebElement]:
    """Return the first element whose CSS selector matches."""

    selector_list = list(selectors)
    if not selector_list:
        return None

    short_timeout = max(5, timeout // len(selector_list))
    for selector in selector_list:
        try:
            wait = WebDriverWait(driver, short_timeout)
            element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            if element:
                return element
        except TimeoutException:
            continue
    return None


def click_element(driver: WebDriver, element: RemoteWebElement) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    element.click()


def open_analytics(driver: WebDriver, video_id: str, timeout: int = DEFAULT_TIMEOUT) -> None:
    analytics_url = (
        f"https://studio.youtube.com/video/{video_id}/analytics/tab-overview/period-default"
    )
    driver.get(analytics_url)
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "ytcp-header"))
    )


def switch_to_advanced_mode(driver: WebDriver) -> None:
    """Switch from the default analytics overview to the advanced view."""

    selectors = (
        'ytcp-button[aria-label="Advanced mode"]',
        'ytcp-button[aria-label="See more"]',
        'ytcp-button[aria-label="高度なモード"]',
        'ytcp-button[aria-label="さらに表示"]',
        'button[aria-label="Advanced mode"]',
        'button[aria-label="See more"]',
        'button[aria-label="高度なモード"]',
        'button[aria-label="さらに表示"]',
    )

    element = wait_for_any_label(driver, selectors)
    if not element:
        raise AutomationError("Could not locate the Advanced mode / See more button.")

    click_element(driver, element)

    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "ytcp-analytics-advanced"))
    )


def export_current_view(driver: WebDriver, *, timeout: int = DEFAULT_TIMEOUT) -> None:
    export_button_selectors = (
        'ytcp-icon-button[aria-label="Export current view"]',
        'ytcp-icon-button[aria-label="現在のビューをエクスポート"]',
        'button[aria-label="Export current view"]',
        'button[aria-label="現在のビューをエクスポート"]',
    )

    export_button = wait_for_any_label(driver, export_button_selectors, timeout=timeout)
    if not export_button:
        raise AutomationError("Could not find the export button on the advanced analytics page.")

    click_element(driver, export_button)

    menu_selectors = (
        'tp-yt-paper-item[aria-label^="CSV" i]',
        'tp-yt-paper-item[aria-label^=".csv" i]',
        'tp-yt-paper-item[aria-label^="カンマ"]',
        'tp-yt-paper-item[aria-label*="CSV"]',
    )

    menu_item = wait_for_any_label(driver, menu_selectors, timeout=timeout)
    if not menu_item:
        raise AutomationError("Could not locate the CSV export menu item.")

    click_element(driver, menu_item)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-url", required=True, help="URL of the YouTube video")
    parser.add_argument(
        "--chrome-driver-path",
        type=pathlib.Path,
        default=None,
        help="Path to the ChromeDriver executable. Defaults to the one on PATH.",
    )
    parser.add_argument(
        "--chrome-binary-path",
        type=pathlib.Path,
        default=None,
        help="Path to the Chrome binary to launch. Uses the system default when omitted.",
    )
    parser.add_argument(
        "--user-data-dir",
        type=pathlib.Path,
        required=True,
        help="Chrome user data directory containing the Google account profile.",
    )
    parser.add_argument(
        "--profile-directory",
        default=None,
        help="Named Chrome profile inside the user data directory (e.g. 'Profile 1').",
    )
    parser.add_argument(
        "--download-dir",
        type=pathlib.Path,
        required=True,
        help="Directory where the CSV export should be saved.",
    )
    parser.add_argument(
        "--wait-after-download",
        type=int,
        default=5,
        help="Seconds to wait after triggering the download to ensure completion.",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    download_dir = args.download_dir.expanduser().resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    user_data_dir = args.user_data_dir.expanduser().resolve()
    if not user_data_dir.exists():
        raise FileNotFoundError(f"Chrome user data directory not found: {user_data_dir}")

    video_id = parse_video_id(args.video_url)

    driver: Optional[WebDriver] = None
    try:
        driver = build_driver(
            chrome_driver_path=args.chrome_driver_path,
            chrome_binary_path=args.chrome_binary_path,
            user_data_dir=user_data_dir,
            profile_directory=args.profile_directory,
            download_dir=download_dir,
        )
        open_analytics(driver, video_id)
        switch_to_advanced_mode(driver)
        export_current_view(driver)
        time.sleep(max(args.wait_after_download, 0))
        return 0
    except (TimeoutException, AutomationError, NoSuchElementException) as exc:
        print(f"Automation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
