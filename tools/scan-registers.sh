#!/bin/sh

if test -z "$1"; then
	echo "Use: $0 <device number 1..6> [<receiver device>]"
	exit 2
fi

Z=`readlink -f "$0"`
HC=`dirname "$Z"`/hidconsole

z='0 1 2 3 4 5 6 7 8 9 a b c d e f'

for x in $z; do
	for y in $z; do
		echo "10 0${1} 81${x}${y} 000000"
	done
done | "$HC" --hidpp $2 | grep -v ' 8F.. ..0[12]' | grep -B 1 '^>> '

for x in $z; do
	for y in $z; do
		echo "10 0${1} 83${x}${y} 000000"
	done
done | "$HC" --hidpp $2 | grep -v ' 8F.. ..0[12]' | grep -B 1 '^>> '
