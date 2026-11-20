# Build

Build on Windows with Python, Node.js and Inno Setup 6. Install `requirements-build.txt`. Build the player with PyInstaller using `--onefile --noconsole --icon assets/app.ico --add-data "assets;assets"`. Use absolute paths for icon and assets if the spec is written in a different folder. Build `src/native_bridge.py` separately as `StreamChromeBridge.exe` with `--onefile --console`; the browser starts this stdio host without a visible terminal. Compile `installer/StreamChromePro.iss` after both executables are in `scratch/dist`.

The installer is per-user. It creates Start menu and optional desktop shortcuts and registers the Native Messaging manifests. It removes those registrations on uninstall. Credentials remain in Windows local application data and are not included in the build.

Do not regenerate the Chromium manifest public key when rebuilding: changing it changes the extension ID and requires updating the host allowlist.
