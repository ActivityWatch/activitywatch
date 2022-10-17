#!/usr/bin/env bash

re_ignore='.*(build|dist|venv|old|other|scripts|node|static).*'

echo -n "Lines of code (excluding test): "
files=$(find | egrep '\.(py|js|ts|rs|vue)$' | egrep -v $re_ignore | grep -v 'test')
echo $files | xargs cat | wc -l

#echo "Files:"
#for file in $files; do
#    echo " - $file"
#done

echo -n " - of which Python code: "
files=$(find | egrep '\.(py)$' | egrep -v $re_ignore | grep -v 'test')
echo $files | xargs cat | wc -l

echo -n " - of which Rust code: "
files=$(find | egrep '\.(rs)$' | egrep -v  $re_ignore | grep -v 'test')
echo $files | xargs cat | wc -l

echo -n " - of which JS/TS code: "
files=$(find | egrep '\.(js|ts)$' | egrep -v $re_ignore | grep -v 'test')
echo $files | xargs cat | wc -l

echo -n " - of which Vue code: "
files=$(find | egrep '\.(vue)$' | egrep -v  $re_ignore | grep -v 'test')
echo $files | xargs cat | wc -l

echo -ne "\nLines of test: "
files=$(find | egrep '\.(py|js|vue)$' | egrep -v $re_ignore | grep 'test')
echo $files | xargs cat | wc -l
