#!/bin/bash -e

cabal=`ls *.cabal`

git stash
hackage-cli sync-cabal --incr-rev $cabal
rev=$(sed -n 's/^x-revision: *\([0-9]*\)/\1/p' $cabal)
echo "This is revision $rev"
git checkout $cabal
sed -i "/^[vV]ersion:/a x-revision:          $rev" $cabal
git commit -m "Bump to revision $rev" $cabal
git stash pop

ver=$(sed -n -e 's/^[vV]ersion:\s\+\(.\+\)/\1/p' *.cabal)
tag_name="$ver-r$rev"
git tag --annotate --sign -u ben@smart-cactus.org -m "Release revision $ver" ${tag_name}
hackage-cli push-cabal $cabal
