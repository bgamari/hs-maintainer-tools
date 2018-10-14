#!/usr/bin/env bash

set -e

cabal=`ls *.cabal`

git stash
if ! git diff --quiet; then
    echo "Stopping due to dirty working tree."
    exit 1
fi

hackage-cli sync-cabal --incr-rev $cabal
rev=$(sed -n 's/^x-revision: *\([0-9]*\)/\1/p' $cabal)
echo "This is revision $rev"
git checkout $cabal

sed -i "/^[vV]ersion:/a x-revision:          $rev" $cabal
git commit -m "Bump to revision $rev" $cabal

infer_tag_name() {
    local with_vs=$(git tag | grep 'v[0-9]\+\.[0-9]\+' | wc -l)
    local without_vs=$(git tag | grep '[0-9]\+\.[0-9]\+' | wc -l)
    if [[ $with_vs > $without_vs ]]; then
        echo "v${ver}"
    else
        echo "${ver}"
    fi
}

ver="$(sed -n -e 's/^[vV]ersion:\s\+\(.\+\)/\1/p' *.cabal)-r$rev"
echo "Tagging $ver"
tag_name=$(infer_tag_name)
git tag --annotate --sign -u ben@smart-cactus.org -m "Release revision $ver" ${tag_name}

echo "Pushing to Hackage"
hackage-cli push-cabal $cabal

git push origin $tag_name
