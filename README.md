# GTA 6 Map Overlay

Draws every collectible from MapGenie (cards, Waink locations, exploration, activities, stunts) on top of your in-game map. It reads your game's picture from a video device (a capture card such as an Elgato, or the OBS Virtual Camera), works out where the map is, and places the markers. It does not read your screen, and OBS is not required. Click a marker for its description and screenshots, right-click to mark it found.

## For players

1. Download `GTA6MapOverlay.exe` from the [Releases](../../releases) page and run it.
   Windows SmartScreen may warn about an unknown publisher the first time: choose **More info > Run anyway**.
2. On first launch it downloads the map data once (reference maps, locations, screenshots). Updates after that are automatic.
3. Open the in-game map and keep it on screen.
4. Open the **Settings** tab and pick your video device under **Video source** (press **Scan** if it isn't listed). This is the device that carries your game's picture, for example your Elgato capture card. When the map is found, the status at the top turns green.

| Hotkey | Action |
| --- | --- |
| Ctrl+Alt+S | Show / hide the settings window |
| Ctrl+Alt+H | Show / hide the overlay |
| Ctrl+Alt+M | Turn marker clicking on / off |
| Ctrl+Alt+F | Show / hide collected markers |
| Ctrl+Alt+Z | Undo the last marked item |

Closing the window keeps the overlay running in the system tray. Right-click the tray icon to quit.

Everything the app saves lives in `%APPDATA%\GTA6MapOverlay` (settings, your progress in `found.json`, the log, and the downloaded `data` folder). **Settings > Open data folder** jumps there. Progress from the older script (`found_cards.json`) can be loaded with **Import progress**.

## For the maintainer

### One-time setup

1. Create a **public** GitHub repository and push this project to it.
2. Edit the top of `gta6overlay/config.py`:
   - `GITHUB_REPO` - your `owner/repo`
   - `YOUTUBE_URL` - your channel link
   - `DONATE_URL` - your donate page (the Donate button is hidden while this is empty)

### Publish an app update

```
git tag v1.1.0
git push origin v1.1.0
```

GitHub Actions builds `GTA6MapOverlay.exe` on Windows, runs a smoke test, writes the checksum, and creates the release. The version number comes from the tag. Every user's app picks it up on its next start.

### Publish new map data

Data updates are separate from app updates, so changing locations or screenshots never needs a new exe.

1. In the browser console on the MapGenie map page, run `tools/capture_refs.js` (reference map images), `tools/export_info.js` (descriptions) and `tools/export_extras.js` (extra marker types). Collect the downloads in one folder.
2. In that folder run `python <repo>/tools/download_media.py` to fetch the screenshots into `card_media/`.
3. Build the pack (this extracts the tracking features once so players never have to):

   ```
   pip install -r requirements.txt
   python tools/build_data_pack.py --version 2 --source <folder> --out dist-data
   ```

4. Publish the command it prints, for example:

   ```
   gh release create data-2 dist-data/data-pack.zip dist-data/data-pack.zip.sha256 --title "Map data 2"
   ```

The data version is the number in the tag (`data-2`). Players with an older version download the new pack automatically. Images are never baked into the exe: roughly 1,500 screenshots plus the reference features live in `data-pack.zip`, downloaded once and replaced only when you publish a new data release.

### How updating works

- On start the app asks the GitHub API for your releases. Tags `vX.Y.Z` are app releases and `data-N` are map data. Drafts and pre-releases are ignored, so you can stage a release as a draft first.
- Downloads must come from GitHub hosts, are checked against a SHA-256 (the asset digest, or the `.sha256` file), and are rejected if anything differs.
- A new exe replaces the running one by renaming (Windows allows this), then the app relaunches. If the folder is not writable the user is told what to do.
- "Update automatically" (on by default, Support tab) installs updates at startup. Turn it off and users get a banner with an **Update now** button instead.

## Development

```
pip install -r requirements.txt
python main.py                  # run from source
python main.py --selftest       # quick check that everything loads
pip install pyinstaller
pyinstaller GTA6MapOverlay.spec # build dist/GTA6MapOverlay.exe
```

Tracking and matching values (feature counts, thresholds, HUD zones, marker shapes) are the commented variables in `gta6overlay/config.py`.
