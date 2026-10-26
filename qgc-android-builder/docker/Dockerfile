#
# QGroundControl android build environment
#

FROM ubuntu:22.04
LABEL authors="Daniel Agar <daniel@agar.ca>, Patrick José Pereira <patrickelectric@gmail.com>"

ARG QT_VERSION=5.15.2
ARG GST_VERSION=1.18.6

ENV ANDROID_ABIS=arm64-v8a
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV QMAKESPEC=android-clang
ENV QT_PATH=/opt/Qt
ENV QT_DESKTOP=${QT_PATH}/${QT_VERSION}/android
ENV QT_TARGET=android
ENV PATH=/usr/lib/ccache:${QT_DESKTOP}/bin:${PATH}

RUN apt-get update && apt-get -y --quiet --no-install-recommends install \
        binutils \
        build-essential \
        ca-certificates \
        ccache \
        g++ \
        gcc \
        git \
        libfontconfig1 \
        locales \
        make \
        openjdk-11-jdk-headless \
        openssl \
        unzip \
        wget \
        zlib1g-dev \
    && apt-get -y autoremove \
    && apt-get clean autoclean \
    && rm -rf /var/lib/apt/lists/{apt,dpkg,cache,log} /tmp/* /var/tmp/*

# Install Qt
COPY install-qt-linux.sh /tmp/qt/
RUN bash /tmp/qt/install-qt-linux.sh

# Android Environment
ENV ANDROID_GST_ROOT=/opt/gstreamer-1.0-android-universal-${GST_VERSION}
ENV ANDROID_SDK_ROOT=/opt/android_sdk
ENV ANDROID_NDK_ROOT=${ANDROID_SDK_ROOT}/ndk/21.4.7075529

RUN wget --quiet https://gstreamer.freedesktop.org/data/pkg/android/${GST_VERSION}/gstreamer-1.0-android-universal-${GST_VERSION}.tar.xz -P /tmp \
    && mkdir ${ANDROID_GST_ROOT} \
    && tar xf /tmp/gstreamer-1.0-android-universal-${GST_VERSION}.tar.xz -C ${ANDROID_GST_ROOT}

RUN wget --quiet https://dl.google.com/android/repository/commandlinetools-linux-9862592_latest.zip \
    && mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools \
    && unzip commandlinetools-linux-9862592_latest.zip -d ${ANDROID_SDK_ROOT}/cmdline-tools \
    && mv ${ANDROID_SDK_ROOT}/cmdline-tools/cmdline-tools ${ANDROID_SDK_ROOT}/cmdline-tools/latest

RUN yes | ${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager \
        "build-tools;28.0.3" \
        "ndk;21.4.7075529" \
        "platforms;android-33"

# Reconfigure locale
RUN locale-gen en_US.UTF-8 && dpkg-reconfigure locales

# create user with id 1000 to not run commands/generate files as root
RUN useradd user --create-home --home-dir /home/user --shell /bin/bash --uid 1000
USER user

WORKDIR /project/build
CMD ["/bin/sh", "-c", "qmake /project/source CONFIG+=installer ANDROID_ABIS=$ANDROID_ABIS && make -j$(nproc)"]
