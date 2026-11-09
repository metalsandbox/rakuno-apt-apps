#!/usr/bin/env python3
"""Verify signature, unit syntax, and APT candidate without installing anything."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
subprocess.run(["gpgv", "--keyring", str(ROOT / "keys/rakuno-apt-apps.gpg"), "repo/dists/stable/InRelease"], check=True)
for deb in (ROOT / "repo/pool").rglob("*.deb"):
    subprocess.run(["dpkg-deb", "--info", str(deb)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["dpkg-deb", "--contents", str(deb)], check=True, stdout=subprocess.DEVNULL)
build_dir = ROOT / "build"
build_dir.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=build_dir) as tmp:
    tmp = Path(tmp)
    upstream = json.loads((ROOT / "repo/upstream.json").read_text())
    version = f"{upstream['tag'][1:]}-{upstream['revision']}"
    package = ROOT / "repo/pool/main/d/ddns-go" / f"ddns-go_{version}_amd64.deb"
    extracted = tmp / "ddns-go"
    subprocess.run(["dpkg-deb", "-x", str(package), str(extracted)], check=True)
    unit_check = tmp / "ddns-go.service"
    unit_text = (extracted / "usr/lib/systemd/system/ddns-go.service").read_text()
    unit_check.write_text(unit_text.replace("ExecStart=/usr/bin/ddns-go", f"ExecStart={extracted}/usr/bin/ddns-go"))
    subprocess.run(["systemd-analyze", "verify", str(unit_check)], check=True)

    (tmp / "lists/partial").mkdir(parents=True)
    (tmp / "cache/archives/partial").mkdir(parents=True)
    (tmp / "status").touch()
    (tmp / "sources.list").write_text(f"deb [signed-by={ROOT}/keys/rakuno-apt-apps.gpg] file:{ROOT}/repo stable main\n")
    opts = ["-o", f"Dir::Etc::sourcelist={tmp}/sources.list", "-o", "Dir::Etc::sourceparts=-", "-o", f"Dir::State={tmp}", "-o", f"Dir::State::status={tmp}/status", "-o", f"Dir::Cache={tmp}/cache", "-o", "APT::Sandbox::User=" + __import__('getpass').getuser(), "-o", "APT::Get::List-Cleanup=0"]
    subprocess.run(["apt-get", *opts, "update"], check=True)
    for name in ("ddns-go", "xperia-flashtool"):
        policy = subprocess.check_output(["apt-cache", *opts, "policy", name], text=True)
        print(policy)
        if "Candidate:" not in policy or "Candidate: (none)" in policy:
            raise RuntimeError(f"APT did not find an installable candidate for {name}")
print("Verified; no packages installed.")
