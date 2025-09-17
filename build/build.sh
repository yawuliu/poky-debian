#!/bin/bash

set -ex
SCRIPTDIR=$(dirname $(realpath "$0"))
TOPDIR=$(cd $SCRIPTDIR/../ > /dev/null && pwd -P)
echo "SCRIPTDIR: $SCRIPTDIR"
echo "TOPDIR: $TOPDIR"

MACHINE=qemuarm64
BUILDDIR=out
export TEMPLATECONF=$TOPDIR/meta-debian/conf/templates/default
echo $TEMPLATECONF
source $TOPDIR/poky/oe-init-build-env $BUILDDIR
cp $SCRIPTDIR/configs/$MACHINE/* $BUILDDIR/conf/

bitbake -f core-image-minimal -c clean