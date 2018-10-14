#!/usr/bin/env bash

set -e

has_docs=1
#sandbox=1
newbuild=1

# haddock upload broken with new-build
if [ $newbuild != 0 ]; then has_docs=0; fi;

name=$(sed -n -e 's/^[nN]ame:\s\+\(.\+\)/\1/p' *.cabal)
old_ver=$(sed -n -e 's/^[vV]ersion:\s\+\(.\+\)/\1/p' *.cabal)

grep -i '^Library' *.cabal || has_docs=0

echo "Package name: $name"
echo "Current version: $old_ver"
echo "Has documentation: $has_docs"

# Utilities
try() {
    $@ || (
        echo
        read -p "command failed; is this okay? [yN] " resp;
        if [ "$resp" != "y" ]; then false; fi
    )
}

try cabal outdated

# Prompt to bump version
read -p "New version [$old_ver]: " ver
if [ "$ver" != "" ]; then
    sed -i -e "s/\(^[vV]ersion:\s\+\)$old_ver/\1$ver/" *.cabal
else
    ver="$old_ver"
fi

try cabal check
cabal clean
if [ -n "$nix" ]; then
    nix build -f shell.nix
elif [ -n "$newbuild" ]; then
    cabal new-build
    try cabal new-test
else
    if [ -n "$sandbox" ]; then
        cabal sandbox delete
        cabal sandbox init
    fi
    cabal install --only-dependencies --enable-tests --force-reinstalls
    cabal configure --enable-tests
    cabal build
    try cabal test
fi

prepare_docs() {
    cabal haddock --hyperlink-source \
            --html-location='http://hackage.haskell.org/package/$pkg/docs' \
            --contents-location='http://hackage.haskell.org/package/$pkg' 

    # Prepare documentation
    cd dist/doc/html
    dest="${name}-${ver}-docs"
    cp -r "$name" "$dest"
    tar -c -v -z --format=ustar -f "${dest}.tar.gz" "$dest"
    cd ../../..
}

if [ $has_docs != 0 ]; then prepare_docs; fi

infer_tag_name() {
    local with_vs=$(git tag | grep 'v[0-9]\+\.[0-9]\+' | wc -l)
    local without_vs=$(git tag | grep '[0-9]\+\.[0-9]\+' | wc -l)
    if [[ $with_vs > $without_vs ]]; then
        echo "v${ver}"
    else
        echo "${ver}"
    fi
}

echo
echo "Release looks good, let's ship it!"
git commit *.cabal -m "Bump to $ver" --edit || true
cabal sdist

read -p "Hackage username: " username
read -s -p "Hackage password: " password
echo
cabal upload --username $username --password $password dist/*-${ver}.tar.gz
read -p "Go have a look at the candidate before proceding"

# Tag release
tag_name=`infer_tag_name`
echo "Tagging ${tag_name}"
git tag --annotate --sign -u ben@smart-cactus.org -m "Release $ver" ${tag_name}
git push origin master ${tag_name}

# Publish
cabal upload --username $username --password $password --publish dist/*-${ver}.tar.gz

# Upload documentation
if [ $has_docs != 0 ]; then
    curl -X PUT -H 'Content-Type: application/x-tar' -H 'Content-Encoding: gzip' \
         --data-binary "@dist/doc/html/${dest}.tar.gz" \
         "https://${username}:${password}@hackage.haskell.org/package/${name}-${ver}/docs" \
        && echo "Documentation upload succeeded."
    echo
fi
echo "Version $ver of package $name released."
