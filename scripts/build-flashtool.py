#!/usr/bin/env python3
"""Package pinned official Linux amd64 release; never install on the host."""
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
from build import ROOT, download, write

VERSION = "0.9.36.0-1rakuno1"
ASSETS = {
    "linux.tar.bz2": (
        "https://github.com/Androxyde/Flashtool/releases/download/0.9.36.0/Flashtool-0.9.36.0.tar.bz2",
        "940a0450a5c7f83a686918c58cf8fee101e89f149af51a142aa763a580025b68"),
    "devices.tar.gz": (
        "https://github.com/Androxyde/devices/archive/4f354572579e62337d56a6b9319f7f8b31b3378a.tar.gz",
        "08819efa9a7d06aefd89d02dbd1194586a9c10d57fe01b94f58970bd3c24978f"),
}

def unpack(name, destination):
    url, expected = ASSETS[name]
    cache = ROOT / "downloads" / name
    data = cache.read_bytes() if cache.exists() else download(url)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Pinned upstream SHA256 mismatch: {name}")
    write(cache, data)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        # Python 3.12 data filter rejects escaping links and special files.
        archive.extractall(destination, filter="data")

def main():
    output = ROOT / f"repo/pool/main/x/xperia-flashtool/xperia-flashtool_{VERSION}_amd64.deb"
    if output.exists():
        print(f"Preserving published {output.name}")
        return
    work = ROOT / "build/flashtool"
    if work.exists():
        shutil.rmtree(work)
    unpack("linux.tar.bz2", work / "upstream")
    unpack("devices.tar.gz", work / "devices")
    stage = work / "stage"
    base = stage / "usr/lib/xperia-flashtool"
    shutil.copytree(work / "upstream/FlashTool", base, symlinks=True)
    # We use a launcher with quoted paths and normal local desktop USB access.
    (base / "FlashTool").unlink()
    java = (base / "jre/bin/java").read_bytes()
    if java[:6] != b"\x7fELF\x02\x01" or int.from_bytes(java[18:20], "little") != 62:
        raise ValueError("Expected Linux amd64 Java")
    devices = next((work / "devices").iterdir())
    if not (devices / "C69XX").is_dir():
        raise ValueError("Missing Xperia Z1 device definitions")
    shutil.copytree(devices, stage / "usr/share/xperia-flashtool/devices", symlinks=True)
    files = {
        "xperia-flashtool": ("usr/bin/xperia-flashtool", 0o755),
        "xperia-flashtool.desktop": ("usr/share/applications/xperia-flashtool.desktop", 0o644),
        "70-xperia-flashtool.rules": ("usr/lib/udev/rules.d/70-xperia-flashtool.rules", 0o644),
        "postinst": ("DEBIAN/postinst", 0o755),
        "copyright": ("usr/share/doc/xperia-flashtool/copyright", 0o644),
    }
    for name, (target, mode) in files.items():
        write(stage / target, (ROOT / "packaging/flashtool" / name).read_bytes(), mode)
    write(stage / "usr/share/doc/xperia-flashtool/UPSTREAM", """Official upstream Linux bundle, including its Java 17 runtime and library notices.
Source: https://github.com/Androxyde/Flashtool/tree/29709d7e6291d8aacd496688708f77a4fc89daec
Devices: https://github.com/Androxyde/devices/tree/4f354572579e62337d56a6b9319f7f8b31b3378a
SHA256 values pinned in scripts/build-flashtool.py (HTTPS origin verification,
not an independent upstream signature). Firmware is not included.
""")
    write(stage / "DEBIAN/control", f"""Package: xperia-flashtool
Version: {VERSION}
Section: devel
Priority: optional
Architecture: amd64
Maintainer: metalsandbox <metalsandbox@users.noreply.github.com>
Depends: libc6 (>= 2.34), libstdc++6, zlib1g, libgtk-3-0t64, libxtst6, libxi6, libxrender1, libasound2t64, libfreetype6, libfontconfig1, libusb-1.0-0, libudev1, udev, ca-certificates
Homepage: https://github.com/Androxyde/Flashtool
Description: Sony Xperia S1 firmware flasher (official Linux bundle)
 Official amd64 release with bundled Java, offline device database,
 desktop launcher and local-session USB access rules. Targets Debian 13.
 Firmware flashing is only performed when explicitly started in the GUI.
""")
    # Include corresponding upstream source next to the binary distribution.
    source = download("https://github.com/Androxyde/Flashtool/archive/29709d7e6291d8aacd496688708f77a4fc89daec.tar.gz")
    write(output.parent / "xperia-flashtool_0.9.36.0.upstream-source.tar.gz", source)
    write(output.parent / "xperia-flashtool_devices-source.tar.gz", (ROOT / "downloads/devices.tar.gz").read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(stage), str(output)], check=True)

if __name__ == "__main__":
    main()
