#!/usr/bin/env python3
"""Package verified upstream assets and emit an unsigned APT tree. No pip packages."""
import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "https://api.github.com/repos/jeessy2/ddns-go/releases/"
ARCHES = {"amd64": "x86_64", "arm64": "arm64"}

def download(url):
    headers = {"User-Agent": "metalsandbox-rakuno-apt-apps"}
    if url.startswith("https://api.github.com/") and os.getenv("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as response:
        return response.read()

def run(*args):
    return subprocess.check_output(args, text=True)

def write(path, data, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data)
    else:
        path.write_bytes(data)
    if mode:
        path.chmod(mode)

def build(tag, revision):
    release = json.loads(download(UPSTREAM + ("tags/" + tag if tag else "latest")))
    tag = release["tag_name"]
    if release["draft"] or release["prerelease"] or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Only stable numeric upstream releases are accepted")
    version = tag[1:]
    debversion = version + "-" + revision
    assets = {asset["name"]: asset for asset in release["assets"]}
    sums = download(assets["checksums.txt"]["browser_download_url"]).decode()
    checksums = {parts[1].lstrip("*"): parts[0] for line in sums.splitlines() if len(parts := line.split()) == 2}
    repo = ROOT / "repo"
    for arch, upstream_arch in ARCHES.items():
        name = f"ddns-go_{version}_linux_{upstream_arch}.tar.gz"
        asset = assets[name]
        data = download(asset["browser_download_url"])
        digest = hashlib.sha256(data).hexdigest()
        if digest != checksums.get(name):
            raise ValueError(f"Upstream checksum mismatch: {name}")
        if asset.get("digest") and asset["digest"] != "sha256:" + digest:
            raise ValueError(f"GitHub asset digest mismatch: {name}")
        stage = ROOT / "build" / arch
        if stage.exists():
            shutil.rmtree(stage)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for basename, dest, mode in [("ddns-go", "usr/bin/ddns-go", 0o755), ("LICENSE", "usr/share/doc/ddns-go/copyright", 0o644)]:
                members = [m for m in archive.getmembers() if Path(m.name).name == basename and m.isfile()]
                if len(members) != 1:
                    raise ValueError(f"Missing or ambiguous {basename}")
                write(stage / dest, archive.extractfile(members[0]).read(), mode)
        binary = (stage / "usr/bin/ddns-go").read_bytes()
        if binary[:6] != b"\x7fELF\x02\x01" or int.from_bytes(binary[18:20], "little") != {"amd64": 62, "arm64": 183}[arch]:
            raise ValueError("Unexpected ELF architecture")
        write(stage / "usr/lib/systemd/system/ddns-go.service", (ROOT / "packaging/ddns-go.service").read_text(), 0o644)
        for script in ("postinst", "prerm", "postrm"):
            write(stage / "DEBIAN" / script, (ROOT / "packaging" / script).read_text(), 0o755)
        control = f"""Package: ddns-go
Version: {debversion}
Section: net
Priority: optional
Architecture: {arch}
Maintainer: metalsandbox <metalsandbox@users.noreply.github.com>
Depends: ca-certificates, systemd (>= 245)
Homepage: https://github.com/jeessy2/ddns-go
Description: Simple dynamic DNS client
 Upstream ddns-go binary packaged with a sandboxed systemd service.
 Configuration listens on localhost:9876 and is retained across removal.
"""
        write(stage / "DEBIAN/control", control)
        output = repo / "pool/main/d/ddns-go" / f"ddns-go_{debversion}_{arch}.deb"
        output.parent.mkdir(parents=True, exist_ok=True)
        # Published versions are immutable; bump --revision for packaging changes.
        if not output.exists():
            subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(stage), str(output)], check=True)
        else:
            print(f"Preserving published package {output.name}")
    write(repo / "upstream.json", json.dumps({"tag": tag, "revision": revision}, indent=2) + "\n")
    print(f"Built {debversion}")

def index():
    repo = ROOT / "repo"
    for arch in ARCHES:
        entries = []
        for package in sorted((repo / "pool").rglob(f"*_{arch}.deb")):
            # Keep historical artifacts, but only index the selected Z1-compatible version.
            if package.name.startswith("xperia-flashtool_") and "_0.9.22.3-1rakuno1_" not in package.name:
                continue
            if package.name.startswith("xperia-flashtool-legacy_"):
                continue
            data = package.read_bytes()
            entries.append(run("dpkg-deb", "--field", str(package)).rstrip() + f"\nFilename: {package.relative_to(repo)}\nSize: {len(data)}\nSHA256: {hashlib.sha256(data).hexdigest()}\n\n")
        packages = "".join(entries).encode()
        directory = repo / f"dists/stable/main/binary-{arch}"
        write(directory / "Packages", packages)
        write(directory / "Packages.gz", gzip.compress(packages, mtime=0))
    dist = repo / "dists/stable"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    release_text = f"""Origin: metalsandbox
Label: rakuno-apt-apps
Suite: stable
Codename: stable
Date: {now}
Architectures: amd64 arm64
Components: main
Description: Rakuno apps and Debian packages
SHA256:
"""
    for path in sorted(dist.rglob("Packages*")):
        data = path.read_bytes()
        release_text += f" {hashlib.sha256(data).hexdigest()} {len(data):16d} {path.relative_to(dist)}\n"
    write(dist / "Release", release_text)
    write(repo / "rakuno-apt-apps.gpg", (ROOT / "keys/rakuno-apt-apps.gpg").read_bytes())
    write(repo / "index.html", '<!doctype html><meta charset="utf-8"><title>Rakuno APT Apps</title><h1>Rakuno APT Apps</h1><p><a href="https://github.com/metalsandbox/rakuno-apt-apps#readme">Installation and signing fingerprint</a></p>')
    write(repo / ".nojekyll", "")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="")
    parser.add_argument("--revision", default="1")
    args = parser.parse_args()
    if not re.fullmatch(r"[1-9][0-9]*", args.revision):
        parser.error("revision must be a positive integer")
    build(args.tag, args.revision)
    index()
