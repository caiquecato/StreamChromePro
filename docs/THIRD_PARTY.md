# Third-party software

## FFmpeg 9.0.2 essentials

FFmpeg and FFprobe are installed in the application's `ffmpeg` folder. The executables are unmodified Gyan Windows essentials binaries, licensed under GPLv3. The original license, build configuration and source revision are installed alongside them.

- Binary provider: https://www.gyan.dev/ffmpeg/builds/
- Source revision: https://github.com/FFmpeg/FFmpeg/commit/946fcce07b
- FFmpeg source archive: included in the release downloads.
- External library list and configuration: `ffmpeg/README.txt` in the installed application.
- Build dependencies and upstream sources: https://www.gyan.dev/ffmpeg/builds/#libraries

FFmpeg is run as a separate executable. Its license does not replace the licenses of Python, Pillow or pystray.

## yt-dlp

Video downloading uses the official [yt-dlp](https://github.com/yt-dlp/yt-dlp) executable, version 2026.10.26. yt-dlp is maintained by its contributors and licensed under the Unlicense. Its bundled components carry their own licenses. `LICENSE` and `THIRD_PARTY_LICENSES.txt` are installed in the application's `yt-dlp` folder. The source archive is provided in the release downloads.

## Deno

[Deno](https://github.com/denoland/deno) provides the JavaScript runtime used by supported video extractors. Its MIT license is installed as `yt-dlp/DENO-LICENSE.md`.
