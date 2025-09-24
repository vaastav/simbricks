#!/bin/bash -eux

ls -l /bin/sh
cd /bin
rm sh
ln -s bash sh

apt-get update
apt-get -y install \
  autoconf2.69 \
  bison \
  build-essential \
  chrony \
  cmake \
  file \
  git \
  libncurses-dev \
  linuxptp \
  yarnpkg