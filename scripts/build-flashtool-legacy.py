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
    output = ROOT / f"repo/pool/main/x/xperia-flashtool-legacy/xperia-flashtool-legacy_{VERSION}_amd64.deb"
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
    base = stage / "usr/lib/xperia-flashtool-legacy"
    shutil.copytree(work / "upstream/FlashTool", base, symlinks=True)
    with zipfile.ZipFile(base / "x10flasher.jar") as jar:
        manifest = jar.read("META-INF/MANIFEST.MF")
        if b"Internal-Version: 0.9.22.3" not in manifest:
            raise ValueError("Unexpected internal program version")
        for name in jar.namelist():
            if name.endswith(".class") and b"The bundle does not match the connected device" in jar.read(name):
                raise ValueError("Unexpected model-string rejection in legacy binary")
    # Only remove unused 32-bit payloads; do not patch program JARs or firmware.
    for relative in ("x10flasher_lib/linjre32", "x10flasher_lib/linux/lib32", "x10flasher_lib/swtlin/x86"):
        shutil.rmtree(base / relative)
    for relative in ("FlashTool", "FlashToolConsole"):
        (base / relative).unlink()
    java = (base / "x10flasher_lib/linjre64/bin/java").read_bytes()
    if java[:6] != b"\x7fELF\x02\x01" or int.from_bytes(java[18:20], "little") != 62:
        raise ValueError("Expected amd64 Java runtime")
    write(stage / "usr/bin/xperia-flashtool-legacy", (ROOT / "packaging/flashtool/xperia-flashtool-legacy").read_bytes(), 0o755)
    write(stage / "usr/share/applications/xperia-flashtool-legacy.desktop", """[Desktop Entry]
Type=Application
Name=Xperia Flashtool Legacy 0.9.22.3
Comment=Legacy Sony Xperia Z1 recovery tool
Exec=xperia-flashtool-legacy
Terminal=false
Categories=System;
""", 0o644)
    write(stage / "usr/share/doc/xperia-flashtool-legacy/copyright", (ROOT / "packaging/flashtool/copyright").read_bytes())
    write(stage / "usr/share/doc/xperia-flashtool-legacy/UPSTREAM", f"""Internal upstream version: 0.9.22.3, built 2016-06-08.
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
    write(stage / "DEBIAN/control", f"""Package: xperia-flashtool-legacy
Version: {VERSION}
Section: devel
Priority: optional
Architecture: amd64
Maintainer: metalsandbox <metalsandbox@users.noreply.github.com>
Depends: xperia-flashtool (>= 0.9.36.0-1rakuno1), libgtk2.0-0t64
Homepage: https://github.com/Androxyde/Flashtool
Description: Legacy Xperia Flashtool 0.9.22.3 for S1 devices
 Archived Linux amd64 program with bundled Java 8, separate launcher and
 shared offline device database and USB rules from xperia-flashtool.
 It predates the later strict firmware/device model-string check.
""")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(stage), str(output)], check=True)

if __name__ == "__main__":
    main()
