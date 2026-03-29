import sys

if sys.platform == "win32":
    from .windows import WindowsPlatform as Platform
else:
    from .linux import LinuxPlatform as Platform

platform = Platform()
