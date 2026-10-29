Usage: build-qgc5 [QGC_ROOT] [options]

Build a QGroundControl 5 checkout (CMake/Qt 6) inside Docker, using that
checkout's own deploy/docker builder image.

Arguments:
    QGC_ROOT              QGroundControl 5 checkout. Default: the current
                          directory or its nearest QGC 5 parent.

Options:
    -b, --build-type TYPE Release (default), Debug, RelWithDebInfo, MinSizeRel
    --variant NAME        deploy/docker variant (default: ubuntu)
    -j, --jobs N          Parallel build jobs (default: all cores)
    --build-dir DIR       Build output directory (default: <root>/build,
                          or <root>/build-aarch64 for the aarch64 variant)
    --image NAME          Docker image tag (default: the variant's image)
    --clean               Remove the build directory before building
    --rebuild-image       Rebuild the Docker image without the build cache
    --list-variants       List the checkout's variants and exit
    -h, --help            Show this message and exit

Variants:
    ubuntu, ubuntu-2204, ubuntu-2604, debian, fedora, arch, aarch64, android

Exit codes:
    0  build succeeded
    1  docker is missing, the image build failed, or the QGC build failed
    2  bad usage, or QGC_ROOT is not a QGroundControl 5 checkout
