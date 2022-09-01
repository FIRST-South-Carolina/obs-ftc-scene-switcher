# FTC Scene Switcher

FTC Scene Switcher is an [OBS Studio](https://obsproject.com/) script for [FIRST Tech Challenge](https://www.firstinspires.org/robotics/ftc) events that can automatically switch OBS scenes based on match events from the FTCLive scoring system.

Keep the OBS "Script Log" open to see output from events, hotkeys, and settings buttons.


## OBS Scripting Setup

The FTC Scene Switcher script requires [OBS Studio](https://obsproject.com/) and Python 3.6+. OBS Studio supports current Python versions now on Windows, so grab the latest stable "Windows installer (64-bit)" build available at [python.org](https://www.python.org/ftp/python/3.10.6/python-3.10.6-amd64.exe). From the OBS Studio software, select "Tools" from the menu bar and "Scripts" from the menu, go to the "Python Settings" tab, and select the base prefix for Python 3.6+. For Windows, the base prefix will be `%LOCALAPPDATA%\Programs\Python\Python310` (for Python 3.10). To load one of the scripts below, go back to the "Scripts" tab and click the "+" in the lower-left and navigate to the appropriate script file.


## FTC Scene Switcher Setup

To set up FTC Scene Switcher for subsequent use (as in this only needs to be done once per system), the `websockets` Python package must be installed. To install it in Windows, open a PowerShell or CMD command prompt and run the command `%LOCALAPPDATA%\Programs\Python\Python310\Scripts\pip.exe install -U websockets` (for Python 3.10).


## OBS Profile Setup

Load `ftc-scene-switcher.py` into OBS Studio. Go to the OBS settings by selecting "File" from the menu bar and "Settings" from the menu. Go to the "Hotkeys" section and assign hotkeys for the actions that start with "(FTC)" by selecting the box to the right of the action description and pressing the desired key combination. These will be saved for later when this script is loaded again.


## Usage

Load `ftc-scene-switcher.py` into OBS Studio (if not already loaded). In the script configuration section, add details for the following:

* Enabled - whether the scene switcher is enabled
* Override Non-Match Scenes - whether the scene switcher will switch from non-match-related scenes when receiving a match event
* Scorekeeper WS - address to the `MatchEventStream` API endpoint for the scorekeeper; default is "ws://localhost/api/v2/stream/" which will generally only need to be changed if the FTCLive software is running on another machine
* Match Post Time to Match Wait - time after a match score is posted before the scene is switched to match wait scene (-1 to disable)

* Match Load - scene name to show when a match is loaded
* Match Start - scene name to show when a match is started
* Match Abort - scene name to show when a match is aborted
* Match Commit - scene name to show when a match score is committed
* Match Post - scene name to show when a match score is posted
* Match Wait - scene name to show after a specified timer after a match score is posted
