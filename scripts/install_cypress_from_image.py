"""Install pinned Cypress/Xvfb from the official image without its large browser layers.

Uses the configured HTTPS proxy and system CA trust. No Docker daemon is needed.
Run the normal Cypress installer first when its download host is available.
"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPOSITORY = "cypress/included"
VERSION = "16.2.1"
REGISTRY = "https://registry-1.docker.io/v2/" + REPOSITORY + "/"
ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


def main():
    if os.uname().sysname != "Linux" or os.uname().machine != "x86_64":
        raise SystemExit("This fallback installs the Linux amd64 runtime only.")
    auth = "https://auth.docker.io/token?" + urlencode(
        {"service": "registry.docker.io", "scope": f"repository:{REPOSITORY}:pull"}
    )
    with urlopen(auth, timeout=60) as response:
        token = json.load(response)["token"]

    def request(path):
        return urlopen(
            Request(
                REGISTRY + path,
                headers={"Authorization": "Bearer " + token, "Accept": ACCEPT},
            ),
            timeout=60,
        )

    def document(path):
        with request(path) as response:
            return json.load(response)

    manifest = document("manifests/" + VERSION)
    if "manifests" in manifest:
        platform = next(
            item
            for item in manifest["manifests"]
            if item.get("platform", {}).get("os") == "linux"
            and item["platform"]["architecture"] == "amd64"
        )
        manifest = document("manifests/" + platform["digest"])
    config = document("blobs/" + manifest["config"]["digest"])
    layers = iter(manifest["layers"])
    cypress_layer = dependency_layer = None
    for history in config["history"]:
        if history.get("empty_layer", False):
            continue
        layer = next(layers)
        command = history.get("created_by", "")
        if "/opt/installScripts/cypress/install.sh" in command:
            cypress_layer = layer
        if "apt-get install" in command and "xvfb" in command:
            dependency_layer = layer
    if not cypress_layer or not dependency_layer:
        raise SystemExit("Official image layout changed; inspect before installing.")

    cache = Path.home() / ".cache/Cypress"
    local_bin = Path.home() / ".local/bin"
    cache.mkdir(parents=True, exist_ok=True)
    local_bin.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="washday-cypress-") as directory:

        def download(layer, name):
            target = Path(directory) / name
            digest = hashlib.sha256()
            with (
                request("blobs/" + layer["digest"]) as response,
                target.open("wb") as output,
            ):
                while chunk := response.read(4 * 1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
            if "sha256:" + digest.hexdigest() != layer["digest"]:
                raise SystemExit("Image layer digest mismatch; refusing extraction.")
            return target

        archive = download(cypress_layer, "cypress.tar.gz")
        installed = 0
        with tarfile.open(archive) as tar:
            for member in tar:
                marker = f"/{VERSION}/Cypress"
                name = "/" + member.name
                if marker not in name:
                    continue
                member.name = f"{VERSION}/Cypress" + name.split(marker, 1)[1]
                if ".." in PurePosixPath(member.name).parts:
                    raise SystemExit("Unsafe archive member; refusing extraction.")
                tar.extract(member, path=cache, filter="data")
                installed += 1
        if not (cache / VERSION / "Cypress/Cypress").is_file():
            raise SystemExit("Cypress executable absent after extraction.")

        if not shutil.which("Xvfb"):
            archive = download(dependency_layer, "dependencies.tar.gz")
            with tarfile.open(archive) as tar:
                member = next(
                    item for item in tar if item.name.lstrip("./") == "usr/bin/Xvfb"
                )
                with (
                    tar.extractfile(member) as source,
                    (local_bin / "Xvfb").open("wb") as output,
                ):
                    shutil.copyfileobj(source, output)
                (local_bin / "Xvfb").chmod(0o755)

    print(
        json.dumps(
            {
                "image": REPOSITORY + ":" + VERSION,
                "image_config": manifest["config"]["digest"],
                "cypress_layer": cypress_layer["digest"],
                "dependencies_layer": dependency_layer["digest"],
                "sha256_verified": True,
                "files": installed,
                "cache": str(cache),
            },
            indent=2,
        )
    )
    print('Ensure "$HOME/.local/bin" is on PATH, then run npx cypress verify.')


if __name__ == "__main__":
    main()
