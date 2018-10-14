#!/usr/bin/env python3

from pathlib import Path
from typing import NewType, List, Callable
import shutil
import subprocess
from subprocess import check_call, check_output
import sys
import re

DEFAULT_KEY = "ben@smart-cactus.org"

class CabalFile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get_field(self, field: str) -> str:
        m = re.search(r'^{field}:\s+(.+)([^\s]+)'.format(field=field),
                      self.path.read_text())
        if m is None:
            raise RuntimeError(f"Failed to find value for field {field}")
        else:
            return m.group(0)

    def get_name(self) -> str:
        return self.get_field("name")

    def get_version(self) -> str:
        return self.get_field("version")

    def set_version(self, new_version) -> None:
        old_version = self.get_version()
        content = self.path.read_text()
        conten = re.sub(r"\(^[vV]ersion:\s\+\){old_version}".format(old_version=old_version),
                        r"\1{new_version}".format(new_version=new_version),
                        content)
        self.path.write_text(content)

    def has_library(self) -> bool:
        return re.search('^[lL]ibrary', self.path.read_text()) is not None

def find_cabal_file() -> CabalFile:
    cabals = list(Path('.').glob('*.cabal'))
    if len(cabals) == 0:
        raise RuntimeError('No cabal files in current directory')
    elif len(cabals) > 1:
        raise RuntimeError('More than one cabal file in current directory')
    else:
        return CabalFile(cabals[0])

def try_call(cmd: List[str]) -> None:
    if subprocess.call(cmd) != 0:
        resp = input("command failed; is this okay? [yN] ")
        if resp != "y":
            sys.exit(1)

def prepare_docs(cabal: CabalFile) -> Path:
    name = cabal.get_name()
    ver = cabal.get_version()
    check_call(['cabal', 'haddock',
                '--hyperlink-source',
                f'--html-location=http://hackage.haskell.org/package/{name}/docs',
                f'--contents-location=http://hackage.haskell.org/package/{name}'])
    dest = Path(f"{name}-{ver}-docs")
    shutil.copytree(Path('dist/doc/html') / name, dest)
    tarball = dest.with_suffix("tar.gz")
    check_call(['tar', '-cvz', '--format=ustar', '-f', tarball, dest])
    shutil.rmtree(dest)
    return tarball

def infer_tag_naming() -> Callable[[str], str]:
    out = check_output(['git', 'tag'])
    with_vs = re.findall(r'v[0-9]+(\.[0-9]+)+', out)
    without_vs = re.findall(r'[0-9]+(\.[0-9]+)+', out)
    if len(with_vs) > len(without_vs):
        return lambda ver: f"v${ver}"
    else:
        return lambda ver: ver

def run(mode: str, make_tag: bool, signing_key: str) -> None:
    assert mode in [ "new-build", "nix" ]
    has_docs = True

    # Haddock upload broken with new-build
    if mode == "new-build":
        has_docs = False

    cabal = find_cabal_file()
    name = cabal.get_name()
    old_ver = cabal.get_version()

    print("Package name:", name)
    print("Current version:", old_ver)
    print("Has documentation:", has_docs)

    try_call(["cabal", "outdated", "--exit-code"])

    new_ver = input(f"New version [{old_ver}]: ")
    if new_ver == "":
        new_ver = old_ver

    # Verify that tag doesn't already exist
    existing_tags = check_output(['git', 'tag']).split('\n')
    tag_name = infer_tag_naming()(new_ver)
    if tag_name in existing_tags:
        print(f'Tag {tag_name} already exists')
        sys.exit(1)

    # Set the version and prepare for build
    cabal.set_version(new_ver)
    try_call(["cabal", "check"])
    check_call(["cabal", "clean"])

    # Build it
    if mode == "nix":
        try_call(["nix", "build", "-f", "shell.nix"])
    elif mode == "new-build":
        check_call(["cabal", "new-build"])
        try_call(["cabal", "new-test"])

    docs_tarball = prepare_docs(cabal) if has_docs else None

    # Commit and build sdist
    print()
    print("Release looks good, let's ship it!")
    check_call(["git", "commit", cabal.path, "-m", f"Bump to {new_ver}", "--edit"])
    check_call(["cabal", "sdist"])
    sdist_tarball = f'dist/{name}-{new_ver}.tar.gz'

    # Upload
    username = input("Hackage user name: ")
    password = input("Hackage password: ")
    print()
    check_call(['cabal', 'upload',
                '--username', username,
                '--password', password,
                sdist_tarball])

    if has_docs:
        check_call(['curl', '-X', 'PUT',
                    '-H', 'Content-Type: application/x-tar',
                    '-H', 'Content-Encoding: gzip',
                    '--data-binary', f'@{docs_tarball}',
                    "https://${username}:${password}@hackage.haskell.org/package/${name}-${ver}/docs"])
        print("Documentation uploaded.")

    # Confirm
    input('Go have a look at the candidate before proceding...')

    # Tag release
    if make_tag:
        print(f"Tagging {tag_name}")
        check_call(['git', 'tag', '--annotate', '--sign', '-u', signing_key,
                    '-m', f'Release {new_ver}', tag_name])
        check_call(['git', 'push', 'origin', 'master', tag_name])

    # Publish
    #check_call(['cabal', 'upload',
    #            '--username', username,
    #            '--password', password,
    #            '--publish',
    #            sdist_tarball])

    print(f"Version {new_ver} of package {name} released.")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mode', type=str, choices=['nix', 'new-build'],
                        help="How to build")
    parser.add_argument('-N', '--no-tag', action='store_true',
                        help="Don't produce a git tag for the release")
    parser.add_argument('-k', '--signing-key', type=str,
                        default=DEFAULT_KEY,
                        help="Key to use to sign the tag")
    args = parser.parse_args()
    run(mode=args.mode, make_tag=not args.no_tag, signing_key=args.signing_key)

if __name__ == '__main__':
    main()
