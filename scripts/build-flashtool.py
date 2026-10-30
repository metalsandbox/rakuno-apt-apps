#!/usr/bin/env python3
"""Package the archived, unpatched upstream 0.9.22.3 Linux amd64 program."""
import hashlib
import io
import shutil
import subprocess
import tarfile
import zipfile
from build import ROOT, download, write

VERSION = "0.9.22.3-1rakuno1"
RELEASE = "https://github.com/metalsandbox/rakuno-apt-apps/releases/download/flashtool-legacy-0.9.22.3/"
SHA256 = "0e75d4843602add2df8f8e20cd3216ab282080901f98929f962d6292f0b515ed"
TAR_SHA256 = "48c231febc544a849c5ab93f79fa52c87a03294199643619cfd33678a0bf5ca5"

def main():
    output = ROOT / f"repo/pool/main/x/xperia-flashtool/xperia-flashtool_{VERSION}_amd64.deb"
    if output.exists():
        print(f"Preserving published {output.name}")
        return
    data = download(RELEASE + "flashtool-0.9.22.3-linux.tar.xz")
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Legacy archive SHA256 mismatch")
    import lzma
    tar = lzma.decompress(data)
    if hashlib.sha256(tar).hexdigest() != TAR_SHA256:
        raise ValueError("Original mirror TAR SHA256 mismatch")
    work = ROOT / "build/flashtool-legacy"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(tar)) as archive:
        archive.extractall(work / "upstream", filter="data")
    stage = work / "stage"
    base = stage / "usr/lib/xperia-flashtool"
    shutil.copytree(work / "upstream/FlashTool", base, symlinks=True)
    with zipfile.ZipFile(base / "x10flasher.jar") as jar:
        manifest = jar.read("META-INF/MANIFEST.MF")
        if b"Internal-Version: 0.9.22.3" not in manifest:
            raise ValueError("Unexpected internal program version")
        for name in jar.namelist():
            if name.endswith(".class") and b"The bundle does not match the connected device" in jar.read(name):
                raise ValueError("Unexpected model-string rejection in legacy binary")
        defaults = jar.read("gui/ressources/config.properties").decode().rstrip() + "\ngitauto=false\n"
        write(stage / "usr/share/xperia-flashtool/defaults.properties", defaults, 0o644)
    devices_url = "https://github.com/Androxyde/devices/archive/4f354572579e62337d56a6b9319f7f8b31b3378a.tar.gz"
    devices_data = download(devices_url)
    if hashlib.sha256(devices_data).hexdigest() != "08819efa9a7d06aefd89d02dbd1194586a9c10d57fe01b94f58970bd3c24978f":
        raise ValueError("Device snapshot SHA256 mismatch")
    with tarfile.open(fileobj=io.BytesIO(devices_data)) as archive:
        archive.extractall(work / "devices", filter="data")
    devices = next((work / "devices").iterdir())
    if not (devices / "C69XX").is_dir():
        raise ValueError("Missing Xperia Z1 database")
    data_stage = work / "data-stage"
    shutil.copytree(devices, data_stage / "usr/share/xperia-flashtool/devices", symlinks=True)
    write(data_stage / "DEBIAN/control", """Package: xperia-flashtool-data
Version: 20230102-1rakuno1
Section: devel
Priority: optional
Architecture: all
Maintainer: metalsandbox <metalsandbox@users.noreply.github.com>
Replaces: xperia-flashtool (>= 0.9.36.0-1rakuno1)
Breaks: xperia-flashtool (>= 0.9.36.0-1rakuno1)
Homepage: https://github.com/Androxyde/devices
Description: Offline device database for Xperia Flashtool
 Fixed upstream snapshot 4f354572579e62337d56a6b9319f7f8b31b3378a.
 Includes Xperia Z1 C69XX and SOL23 definitions; contains no runtime.
""")
    write(data_stage / "usr/share/doc/xperia-flashtool-data/UPSTREAM", devices_url + "\n")
    data_output = ROOT / "repo/pool/main/x/xperia-flashtool-data/xperia-flashtool-data_20230102-1rakuno1_all.deb"
    if not data_output.exists():
        data_output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(data_stage), str(data_output)], check=True)
    for name, target, mode in [
        ("70-xperia-flashtool.rules", "usr/lib/udev/rules.d/70-xperia-flashtool.rules", 0o644),
        ("postinst", "DEBIAN/postinst", 0o755),
    ]:
        write(stage / target, (ROOT / "packaging/flashtool" / name).read_bytes(), mode)
    # Only remove unused 32-bit payloads; do not patch program JARs or firmware.
    for relative in ("x10flasher_lib/linjre32", "x10flasher_lib/linux/lib32", "x10flasher_lib/swtlin/x86"):
        shutil.rmtree(base / relative)
    for relative in ("FlashTool", "FlashToolConsole"):
        (base / relative).unlink()
    java = (base / "x10flasher_lib/linjre64/bin/java").read_bytes()
    if java[:6] != b"\x7fELF\x02\x01" or int.from_bytes(java[18:20], "little") != 62:
        raise ValueError("Expected amd64 Java runtime")
    write(stage / "usr/bin/xperia-flashtool", (ROOT / "packaging/flashtool/xperia-flashtool").read_bytes(), 0o755)
    write(stage / "usr/share/applications/xperia-flashtool.desktop", """[Desktop Entry]
Type=Application
Name=Xperia Flashtool 0.9.22.3
Comment=Legacy Sony Xperia Z1 recovery tool
Exec=xperia-flashtool
Terminal=false
Categories=System;
""", 0o644)
    write(stage / "usr/share/doc/xperia-flashtool/copyright", (ROOT / "packaging/flashtool/copyright").read_bytes())
    write(stage / "usr/share/doc/xperia-flashtool/UPSTREAM", f"""Internal upstream version: 0.9.22.3, built 2016-06-08.
Original mirror: https://androiddatahost.com/k9gep
Mirror ZIP SHA256: e557878710cb06a98d6f0ea46da10fb037329486e9efafecb582f163a3b8f0c2
Original TAR SHA256: {TAR_SHA256}
Recompressed TAR SHA256: {SHA256}
These hashes pin the inspected mirror, not an independent author signature.
The historical MD5 for the original compressed distribution is not used as
verification of this mirror's uncompressed TAR. Program version and absence
of the later strict model-string rejection are also checked at build time.
Upstream source commit: ba0404400a256ee9c0debecdebecf3fec292ea64 (0.9.22.3)
Corresponding source archive: {RELEASE}flashtool-0.9.22.3-source.tar.gz
No firmware files included or modified. No phone operations on installation.
""")
    write(stage / "DEBIAN/control", f"""Package: xperia-flashtool
Version: {VERSION}
Section: devel
Priority: optional
Architecture: amd64
Maintainer: metalsandbox <metalsandbox@users.noreply.github.com>
Depends: xperia-flashtool-data (= 20230102-1rakuno1), libc6 (>= 2.34), libstdc++6, zlib1g, libgtk2.0-0t64, libxtst6, libxi6, libxrender1, libasound2t64, libfreetype6, libfontconfig1, libusb-1.0-0, libudev1, udev, ca-certificates
Homepage: https://github.com/Androxyde/Flashtool
Description: Legacy Xperia Flashtool 0.9.22.3 for S1 devices
 Archived Linux amd64 program with bundled Java 8, separate launcher and
 offline device database and local-session Sony USB rules.
 It predates the later strict firmware/device model-string check.
""")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(stage), str(output)], check=True)

if __name__ == "__main__":
    main()
