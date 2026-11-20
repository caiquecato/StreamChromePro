# Third-party software

## FFmpeg 9.0.2 essentials

FFmpeg and FFprobe are installed in the application's `ffmpeg` folder. The executables are unmodified Gyan Windows essentials binaries, licensed under GPLv3. The original license, build configuration and source revision are installed alongside them.

- Binary provider: https://www.gyan.dev/ffmpeg/builds/
- Source revision: https://github.com/FFmpeg/FFmpeg/commit/946fcce07b
- FFmpeg source archive: included in the release downloads.
- External library list and configuration: `ffmpeg/README.txt` in the installed application.
- Build dependencies and upstream sources: https://www.gyan.dev/ffmpeg/builds/#libraries

FFmpeg is run as a separate executable. Its license does not replace the licenses of Python, Pillow or pystray.
