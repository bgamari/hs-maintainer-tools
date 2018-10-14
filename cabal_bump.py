#!/usr/bin/env python3

from pathlib import Path
from typing import NewType, List, Callable, Optional
import shutil
import subprocess
from subprocess import check_call, check_output
import sys
import re

DEFAULT_KEY = "ben@smart-cactus.org"

class CabalFile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get_field(self, field: str) -> Optional[str]:
        m = re.search(r'^{field}:\s*([^\s]+)'.format(field=field),
                      self.path.read_text(),
                      flags=re.IGNORECASE | re.MULTILINE)
        if m is None:
            return None
        else:
            return m.group(1)

    def get_name(self) -> str:
        name = self.get_field("name")
        if name is None:
            raise RuntimeError(f"Failed to find package name")
        else:
            return name

    def get_version(self) -> str:
        ver = self.get_field("version")
        if ver is None:
            raise RuntimeError(f"Failed to find package version")
        else:
            return ver

    def get_revision(self) -> int:
        rev = self.get_field("x-revision")
        return 0 if rev is None else int(rev)

    def set_field(self, field, new) -> None:
        content = self.path.read_text()
        content = re.sub(r"^(?P<field>{field}:\s*).*(?P<post>\s(--.*)?)".format(field=field),
                         r"\g<field>{new}\g<post>".format(new=new),
                         content,
                         flags=re.IGNORECASE | re.MULTILINE)
        self.path.write_text(content)
        assert self.get_field(field) == new

    def set_version(self, new_version) -> None:
        self.set_field("version", new_version)

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

def get_tags() -> List[str]:
    return check_output(['git', 'tag']).decode('UTF-8').split('\n')

def infer_tag_naming() -> Callable[[str], str]:
    tags = get_tags()
    with_vs = [ tag for tag in tags if re.match(r'v[0-9]+(\.[0-9]+)+', tag) ]
    without_vs = [ tag for tag in tags if re.findall(r'[0-9]+(\.[0-9]+)+', tag) ]
    if len(with_vs) > len(without_vs):
        return lambda ver: f"v${ver}"
    else:
        return lambda ver: ver


def make_tag(version: str, signing_key: str) -> None:
    tag_name = infer_tag_naming()(version)
    print(f"Tagging {tag_name}")
    check_call(['git', 'tag', '--annotate', '--sign', '-u', signing_key,
                '-m', f'Release {version}', tag_name])
    check_call(['git', 'push', 'origin', 'master', tag_name])

def do_revision(cabal: CabalFile, signing_key: str) -> None:
    check_call(['hackage-cli', 'sync-cabal', '--incr-rev', cabal.path])
    ver = cabal.get_version()
    rev = cabal.get_revision()
    print(f'This is revision {rev}')
    full_ver = f'{ver}-r{rev}'
    check_call(['hackage-cli', 'push-cabal', cabal.path])
    make_tag(full_ver, signing_key)
    print(f'Cut revision {full_ver}')

def run(mode: str, omit_tag: bool, signing_key: str) -> None:
    assert mode in [ "new-build", "nix" ]
    has_docs = True

    # Haddock upload broken with new-build
    if mode == "new-build":
        has_docs = False

    if subprocess.call(['git', 'diff', '--quiet']) != 0:
        print('Stopping due to dirty working tree')
        return

    cabal = find_cabal_file()
    name = cabal.get_name()
    old_ver = cabal.get_version()
    mk_tag_name = infer_tag_naming()

    # Check whether there are any significant changes
    old_tag = mk_tag_name(old_ver)
    if old_tag in get_tags():
        changed_files = check_output(['git', 'diff', '--name-only', f'{old_tag}..HEAD'])
        non_cabals = [ f
                       for f in changed_files
                       if not changed_files.endswith('.cabal') ]
        if len(non_cabals) == 0:
            print(f'''
              It appears that the only changes between {old_tag} and now are in the
              cabal file. Perhaps you want to make a revision instead?

              y = make a revision
              n = do a full release anyways
              d = show me a diff
            ''')
            while True:
                resp = input('[ynd] ')
                if resp == 'd':
                    cmd = ['git', 'diff', f'{old_tag}..HEAD']
                    print(' '.join(cmd))
                    check_call(cmd)
                elif resp == 'y':
                    do_revision(cabal, signing_key)
                    return
                elif resp == 'n':
                    break

    print("Package name:", name)
    print("Current version:", old_ver)
    print("Has documentation:", has_docs)

    try_call(["cabal", "outdated", "--exit-code"])

    new_ver = input(f"New version [{old_ver}]: ")
    if new_ver == "":
        new_ver = old_ver

    # Verify that tag doesn't already exist
    existing_tags = get_tags()
    tag_name = mk_tag_name(new_ver)
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
    subprocess.call(["git", "commit", cabal.path, "-m", f"Bump to {new_ver}", "--edit"])
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
    if not omit_tag:
        make_tag(new_ver, signing_key)

    # Publish
    check_call(['cabal', 'upload',
                '--username', username,
                '--password', password,
                '--publish',
                sdist_tarball])

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
    run(mode=args.mode, omit_tag=args.no_tag, signing_key=args.signing_key)

if __name__ == '__main__':
    main()
