#!/bin/sh
set -eu
: "${GNUPGHOME:?Set GNUPGHOME to the dedicated signing key directory}"
fingerprint=6ACB155ED1C7D515F3E032793E73068920447E56
gpg --batch --yes --local-user "$fingerprint" --digest-algo SHA256 --clearsign --output repo/dists/stable/InRelease repo/dists/stable/Release
gpg --batch --yes --local-user "$fingerprint" --digest-algo SHA256 --armor --detach-sign --output repo/dists/stable/Release.gpg repo/dists/stable/Release
gpgv --keyring "$PWD/keys/ddns-go-apt.gpg" repo/dists/stable/InRelease
