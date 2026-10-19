import argparse
import json
import sys
from importlib.metadata import version
from pathlib import Path


def check_conda_stack():
    records = {}
    for record_path in (Path(sys.prefix) / "conda-meta").glob("*.json"):
        record = json.loads(record_path.read_text())
        records[record["name"]] = record
    required = (
        "cuda-version", "cuda-python", "cupy", "libucxx",
        "rmm", "librmm", "cudf", "pylibcudf", "libcudf",
        "cuml", "libcuml", "cugraph", "pylibcugraph", "libcugraph",
        "pylibraft", "libraft", "cuvs", "libcuvs", "libcuspatial",
        "libcublas", "libcufft", "libcurand", "libcusolver", "libcusparse",
    )
    missing = [package for package in required if package not in records]
    if missing:
        raise RuntimeError(f"Missing Conda packages: {missing}")
    for package in ("cuda-version", "cuda-python"):
        if tuple(map(int, records[package]["version"].split(".")[:2])) != (12, 8):
            raise RuntimeError(f"{package}: expected Conda CUDA 12.8, got {records[package]}")
    for package in ("rmm", "cudf", "cuml", "cugraph"):
        record = records[package]
        if "cuda12" not in record["build"]:
            raise RuntimeError(f"{package}: expected Conda CUDA 12 build, got {record}")
        print("Conda {}: {} {}".format(package, record["version"], record["build"]), flush=True)
    print("PASS: Conda CUDA 12.8 stack and native library package records", flush=True)


def check_packages():
    import faiss
    import torch
    import torchvision
    from torchvision.extension import _has_ops

    expected_versions = {
        "torch": "2.7.1+cu128",
        "torchvision": "0.22.1+cu128",
        "faiss": "1.12.0",
        "implicit": "0.7.2",
        "numpy": "1.26.4",
        "pandas": "2.1.4",
        "scipy": "1.11.4",
        "cupy": "13.6.0",
        "numba": "0.60.0",
        "numba-cuda": "0.4.0",
        "pyarrow": "19.0.1",
        "cuda-python": "12.8.0",
    }
    for package, expected in expected_versions.items():
        installed = version(package)
        print(f"{package}: {installed}", flush=True)
        if installed != expected:
            raise RuntimeError(f"{package}: expected {expected}, got {installed}")
    for package in ("cudf", "cuml", "cugraph"):
        installed = version(package)
        print(f"{package}: {installed}", flush=True)
        if tuple(map(int, installed.split(".")[:2])) != (25, 4):
            raise RuntimeError(f"{package}: expected RAPIDS 25.04, got {installed}")
    print(f"PyTorch built CUDA: {torch.version.cuda}", flush=True)
    if torch.version.cuda != "12.8":
        raise RuntimeError("Expected PyTorch CUDA 12.8 wheels")
    if not _has_ops():
        raise RuntimeError("torchvision native operators are unavailable")
    if not hasattr(faiss, "StandardGpuResources"):
        raise RuntimeError("FAISS GPU support is unavailable")
    print(f"torchvision native ops: {torchvision.__version__}", flush=True)


def check_torch(require_blackwell):
    import torch
    import torch.nn.functional as functional
    from torchvision.ops import nms

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; run with --nv and check the host driver")
    print(f"PyTorch compiled architectures: {torch.cuda.get_arch_list()}", flush=True)
    for device_index in range(torch.cuda.device_count()):
        with torch.cuda.device(device_index):
            capability = torch.cuda.get_device_capability()
            print(
                f"GPU {device_index}: {torch.cuda.get_device_name()}, capability={capability}",
                flush=True,
            )
            if require_blackwell and capability != (12, 0):
                raise RuntimeError("Expected an RTX Blackwell GPU with capability 12.0")
            matrix = torch.randn(128, 128, device="cuda", requires_grad=True)
            loss = matrix.square().mean() + (matrix @ matrix.T).square().mean()
            loss.backward()
            if not torch.isfinite(matrix.grad).all().item():
                raise RuntimeError("Non-finite PyTorch gradients")
            features = torch.randn(2, 8, 16, 16, device="cuda", requires_grad=True)
            filters = torch.randn(8, 8, 3, 3, device="cuda", requires_grad=True)
            functional.conv2d(features, filters).square().mean().backward()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                output = matrix @ matrix.T
            if not torch.isfinite(output).all().item():
                raise RuntimeError("Non-finite BF16 output")
            boxes = torch.tensor([[0, 0, 2, 2], [0, 0, 2, 2]], device="cuda", dtype=torch.float32)
            scores = torch.tensor([0.9, 0.8], device="cuda")
            if nms(boxes, scores, 0.5).tolist() != [0]:
                raise RuntimeError("torchvision CUDA NMS failed")
            torch.cuda.synchronize()
    print("PASS: PyTorch forward/backward, cuDNN convolution, BF16, torchvision CUDA NMS", flush=True)


def check_gpu_libraries():
    import cupy
    import cudf
    import cugraph
    import faiss
    import implicit.gpu
    import numpy
    from cuml.cluster import KMeans
    from implicit.gpu.als import AlternatingLeastSquares
    from scipy.sparse import csr_matrix

    values = cupy.arange(16, dtype=cupy.float32)
    if float((values * values).sum().get()) != 1240.0:
        raise RuntimeError("CuPy CUDA kernel failed")
    if int(cudf.Series([1, 2, 3]).sum()) != 6:
        raise RuntimeError("cuDF reduction failed")
    samples = cupy.asarray([[0, 0], [0, 1], [10, 10], [10, 11]], dtype=cupy.float32)
    model = KMeans(n_clusters=2, n_init=1, random_state=0)
    labels = cupy.asarray(model.fit_predict(samples))
    if int(cupy.unique(labels).size) != 2:
        raise RuntimeError("cuML KMeans failed")
    edges = cudf.DataFrame({"src": [0, 1, 2], "dst": [1, 2, 0]})
    graph = cugraph.Graph()
    graph.from_cudf_edgelist(edges, source="src", destination="dst")
    if len(cugraph.pagerank(graph)) != 3:
        raise RuntimeError("cuGraph PageRank failed")
    print("PASS: CuPy, cuDF, cuML, cuGraph", flush=True)

    resources = faiss.StandardGpuResources()
    index = faiss.GpuIndexFlatL2(resources, 2)
    vectors = numpy.asarray([[0, 0], [1, 1], [2, 2]], dtype=numpy.float32)
    index.add(vectors)
    distances, neighbors = index.search(vectors, 1)
    numpy.testing.assert_array_equal(neighbors[:, 0], numpy.arange(3))
    numpy.testing.assert_allclose(distances, 0, atol=1e-5)
    print("PASS: FAISS GPU add/search", flush=True)

    if not implicit.gpu.HAS_CUDA:
        raise RuntimeError("implicit GPU extension is unavailable")
    interactions = csr_matrix(numpy.eye(8, dtype=numpy.float32))
    recommender = AlternatingLeastSquares(factors=4, iterations=1, random_state=0)
    recommender.fit(interactions, show_progress=False)
    if not numpy.isfinite(recommender.user_factors.to_numpy()).all():
        raise RuntimeError("implicit GPU ALS produced non-finite factors")
    cupy.cuda.runtime.deviceSynchronize()
    print("PASS: implicit GPU ALS", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Validate the Blackwell superimage")
    parser.add_argument("--gpu", action="store_true", help="Run actual CUDA kernels")
    parser.add_argument("--require-blackwell", action="store_true", help="Require capability 12.0")
    args = parser.parse_args()
    if args.require_blackwell and not args.gpu:
        parser.error("--require-blackwell requires --gpu")
    check_conda_stack()
    check_packages()
    if args.gpu:
        check_torch(args.require_blackwell)
        check_gpu_libraries()
    print("All requested checks passed", flush=True)


if __name__ == "__main__":
    main()
