#!/bin/bash -e

function check_package() {
    cabal outdated
    if [ -n "$slow" ]; then cabal new-build; fi
}

logs=`pwd`/logs
mkdir -p $logs
if [ -z "$@" ]; then
    dirs="$(find -iname '*.cabal')"
else
    dirs="$@"
fi

cat >$logs/log <<EOF
Checking the following packages
$dirs
===================================
EOF

for i in $dirs; do
    dir=$(dirname $i)
    file=$(basename $i)
    echo
    echo "=== $dir"
    pushd $dir > /dev/null
    check_package $dir 2>&1 | tee $logs/$file
    if [ ${PIPESTATUS[0]} == 0 ]; then
        echo "ok    $dir" >> $logs/log
    else
        echo "fail  $dir" >> $logs/log
    fi
    popd > /dev/null
done

