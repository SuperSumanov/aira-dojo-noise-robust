#!/bin/bash
set -euo pipefail

build_root=$(mktemp -d /tmp/faiss-blackwell.XXXXXX)
trap 'rm -rf "$build_root"' EXIT

git clone --depth 1 --branch v1.12.0 https://github.com/facebookresearch/faiss.git "$build_root/source"
cmake -S "$build_root/source" -B "$build_root/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
    -DCMAKE_CUDA_ARCHITECTURES="86;120" \
    -DFAISS_OPT_LEVEL=generic \
    -DFAISS_ENABLE_GPU=ON \
    -DFAISS_ENABLE_CUVS=OFF \
    -DFAISS_ENABLE_MKL=OFF \
    -DFAISS_ENABLE_PYTHON=ON \
    -DFAISS_ENABLE_EXTRAS=OFF \
    -DBUILD_TESTING=OFF \
    -DPython_EXECUTABLE="$(command -v python)"
cmake --build "$build_root/build" --target swigfaiss --parallel "${BUILD_JOBS:-4}"
cd "$build_root/build/faiss/python"
python -m pip install --no-build-isolation --no-deps .
