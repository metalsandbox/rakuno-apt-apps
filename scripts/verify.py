#!/usr/bin/env python3
"""Verify signature, unit syntax, and APT candidate without installing anything."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
subprocess.run(["gpgv", "--keyring", str(ROOT / "keys/rakuno-apt-apps.gpg"), "repo/dists/stable/InRelease"], check=True)
unit_check = ROOT / "build/unit-check/ddns-go.service"
unit_check.parent.mkdir(parents=True, exist_ok=True)
unit_check.write_text((ROOT / "packaging/ddns-go.service").read_text().replace("ExecStart=/usr/bin/ddns-go", f"ExecStart={ROOT}/build/amd64/usr/bin/ddns-go"))
subprocess.run(["systemd-analyze", "verify", str(unit_check)], check=True)

for deb in (ROOT / "repo/pool").rglob("*.deb"):
    subprocess.run(["dpkg-deb", "--info", str(deb)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["dpkg-deb", "--contents", str(deb)], check=True, stdout=subprocess.DEVNULL)
with tempfile.TemporaryDirectory(dir=ROOT / "build") as tmp:
    tmp = Path(tmp)
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
