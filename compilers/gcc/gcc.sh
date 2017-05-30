#!/bin/bash

cd /mnt/work
cp -r /mnt/in/* /mnt/work/src/

COMP_OPT=$(cat opt/comp_opt)
INJECT_COMP_OPT=$(cat opt/inject_comp_opt)
LINK_OPT=$(cat opt/link_opt)
STRIP_OPT=$(cat opt/strip_opt)
SEQ=1

cd src
find . -type f -name "*.cpp" -o -type f -name "*.c" | while read -r FNAME
do
        BASENAME="${FNAME##*/}"
        TARGET_FNAME="${BASENAME%.*}.$SEQ.o"
        g++ $COMP_OPT -c "$FNAME" -o "../obj/$TARGET_FNAME"

        if [ $? -ne 0 ]
        then
                echo gcc failed >&2
                exit 1
        fi

        if [ "$STRIP_OPT" != "" ]
        then
                strip $STRIP_OPT "../obj/$TARGET_FNAME"

                if [ $? -ne 0 ]
                then
                        echo strip failed >&2
                        exit 2
                fi
        fi

        SEQ=$((SEQ+1))
done
EXIT_CODE=$?
[ $EXIT_CODE -ne 0 ] && exit $EXIT_CODE;

cd ../inject
find . -type f | while read -r FNAME
do
        BASENAME="${FNAME##*/}"
        TARGET_FNAME="${BASENAME%.*}.$SEQ.o"
        g++ $INJECT_COMP_OPT -c "$FNAME" -o "../obj/$TARGET_FNAME"

        if [ $? -ne 0 ]
        then
                echo gcc failed >&2
                exit 2
        fi

        SEQ=$((SEQ+1))
done
EXIT_CODE=$?
[ $EXIT_CODE -ne 0 ] && exit $EXIT_CODE;

cd ..
g++ $LINK_OPT obj/*.o -o prog

if [ $? -ne 0 ]
then
        echo gcc failed >&2
        exit 1
fi

mv prog /mnt/out/prog
