#!/usr/bin/env bash

echo -n "Lines of code (excluding test): "
files=$(find | egrep '\.(py|js|vue)$' | egrep -v '.*(build|dist|venv|old|other|scripts|node|static).*' | grep -v 'test')
echo $files | xargs cat | wc -l

#echo "Files:"
#for file in $files; do
#    echo " - $file"
#done

echo -n " - of which Python code: "
files=$(find | egrep '\.(py)$' | egrep -v '.*(build|dist|venv|old|other|scripts|node|static).*' | grep -v 'test')
echo $files | xargs cat | wc -l

echo -n " - of which JS code: "
files=$(find | egrep '\.(js)$' | egrep -v '.*(build|dist|venv|old|other|scripts|node|static).*' | grep -v 'test')
echo $files | xargs cat | wc -l

echo -n " - of which Vue code: "
files=$(find | egrep '\.(vue)$' | egrep -v '.*(build|dist|venv|old|other|scripts|node|static).*' | grep -v 'test')
echo $files | xargs cat | wc -l

echo -ne "\nLines of test: "
files=$(find | egrep '\.(py|js|vue)$' | egrep -v '.*(build|dist|venv|old|other|scripts|node|static).*' | grep 'test')
echo $files | xargs cat | wc -l
