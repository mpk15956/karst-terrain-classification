"""
GPU Detection and Configuration Utilities

Provides portable GPU detection that works across different systems:
- Systems with NVIDIA GPU + CUDA
- Systems without GPU (CPU-only)
- Multi-platform support (Linux, Windows WSL2, macOS)

Usage:
    from geo_tda.utils.gpu_detection import detect_gpu_config, get_compute_backend

    gpu_info = detect_gpu_config()
    if gpu_info:
        print(f"GPU detected: {gpu_info['device_name']}")
    else:
        print("No GPU detected, using CPU")
"""

import logging
import warnings
from typing import Optional, Dict, Any

log = logging.getLogger(__name__)


def detect_gpu_config() -> Optional[Dict[str, Any]]:
    """
    Detect GPU availability and return configuration information.

    This function attempts to detect NVIDIA CUDA GPUs using PyTorch as the
    detection mechanism. It gracefully handles:
    - No GPU hardware present
    - GPU drivers not installed
    - CUDA libraries not available
    - PyTorch not installed or built without CUDA support

    Returns:
        Dict with GPU info if GPU is available:
            {
                "backend": "cuda",
                "device_count": int,
                "device_name": str,
                "memory_gb": float,
                "memory_available_gb": float,
                "compute_capability": tuple (major, minor),
                "driver_version": str,
                "cuda_version": str
            }
        None if no GPU is available or accessible

    Examples:
        >>> gpu = detect_gpu_config()
        >>> if gpu:
        ...     print(f"Found {gpu['device_count']} GPU(s)")
        ...     print(f"Primary GPU: {gpu['device_name']}")
        ...     print(f"VRAM: {gpu['memory_gb']:.1f} GB")
    """
    try:
        import torch

        if not torch.cuda.is_available():
            log.info("PyTorch installed but CUDA not available (CPU-only build or no GPU)")
            return None

        # Get GPU 0 properties (primary GPU)
        device_props = torch.cuda.get_device_properties(0)

        # Calculate available memory (current free memory)
        try:
            torch.cuda.reset_peak_memory_stats(0)
            memory_available = torch.cuda.mem_get_info(0)[0] / 1e9  # bytes -> GB
        except Exception:
            memory_available = None  # Could not determine available memory

        gpu_info = {
            "backend": "cuda",
            "device_count": torch.cuda.device_count(),
            "device_name": torch.cuda.get_device_name(0),
            "memory_gb": device_props.total_memory / 1e9,
            "memory_available_gb": memory_available,
            "compute_capability": torch.cuda.get_device_capability(0),
            "driver_version": torch.cuda.get_device_properties(0).driver_version,
            "cuda_version": torch.version.cuda,
        }

        log.info(
            f"GPU detected: {gpu_info['device_name']} "
            f"({gpu_info['memory_gb']:.1f} GB VRAM, "
            f"CUDA {gpu_info['cuda_version']})"
        )

        return gpu_info

    except ImportError:
        log.debug("PyTorch not installed, cannot detect GPU")
        return None
    except Exception as e:
        log.debug(f"GPU detection failed: {e}")
        return None


def get_compute_backend(prefer_gpu: bool = True) -> str:
    """
    Determine the appropriate compute backend (GPU or CPU).

    Args:
        prefer_gpu: If True (default), use GPU if available.
                   If False, always return CPU even if GPU exists.

    Returns:
        "cuda" if GPU is available and preferred, otherwise "cpu"

    Examples:
        >>> backend = get_compute_backend()
        >>> print(f"Using {backend} for computation")
    """
    if prefer_gpu:
        gpu_info = detect_gpu_config()
        if gpu_info:
            return "cuda"

    return "cpu"


def check_cupy_available() -> bool:
    """
    Check if CuPy is installed and functional.

    CuPy is used for GPU-accelerated NumPy-like operations.
    This function verifies both installation and CUDA runtime availability.

    Returns:
        True if CuPy can be imported and has CUDA support, False otherwise

    Examples:
        >>> if check_cupy_available():
        ...     import cupy as cp
        ...     # Use CuPy for GPU operations
    """
    try:
        import cupy as cp

        # Test if CUDA runtime is available
        device_count = cp.cuda.runtime.getDeviceCount()
        if device_count > 0:
            log.debug(f"CuPy available with {device_count} CUDA device(s)")
            return True
        else:
            log.debug("CuPy installed but no CUDA devices found")
            return False

    except ImportError:
        log.debug("CuPy not installed")
        return False
    except Exception as e:
        log.debug(f"CuPy check failed: {e}")
        return False


def get_optimal_gpu_memory_fraction(
    gpu_info: Optional[Dict[str, Any]] = None,
    safety_factor: float = 0.8
) -> float:
    """
    Calculate the optimal fraction of GPU memory to use.

    Args:
        gpu_info: GPU configuration dict from detect_gpu_config().
                 If None, will call detect_gpu_config() internally.
        safety_factor: Fraction of available memory to use (0.0-1.0).
                      Default 0.8 reserves 20% buffer for OS/other processes.

    Returns:
        Fraction of GPU memory in bytes that should be used for computation.
        Returns 0.0 if no GPU is available.

    Examples:
        >>> memory_limit = get_optimal_gpu_memory_fraction()
        >>> if memory_limit > 0:
        ...     print(f"Allocating {memory_limit / 1e9:.1f} GB for GPU tasks")
    """
    if gpu_info is None:
        gpu_info = detect_gpu_config()

    if gpu_info is None:
        return 0.0

    # Use available memory if known, otherwise use total memory
    if gpu_info.get("memory_available_gb"):
        base_memory_gb = gpu_info["memory_available_gb"]
    else:
        base_memory_gb = gpu_info["memory_gb"]

    return base_memory_gb * safety_factor * 1e9  # GB -> bytes


def configure_gpu_memory_growth(enable: bool = True) -> bool:
    """
    Configure TensorFlow/PyTorch-style GPU memory growth.

    When enabled, GPU memory is allocated incrementally as needed rather
    than reserving all memory upfront. This allows multiple processes to
    share the GPU more efficiently.

    Args:
        enable: If True, enable memory growth. If False, use default behavior.

    Returns:
        True if configuration succeeded, False otherwise

    Note:
        This primarily affects PyTorch. CuPy uses a different memory model.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return False

        if enable:
            # PyTorch doesn't have exact equivalent to TF's memory growth
            # But we can configure the allocator to be more conservative
            import os
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'
            log.info("Configured PyTorch GPU memory allocator for incremental growth")

        return True

    except ImportError:
        return False
    except Exception as e:
        log.warning(f"Failed to configure GPU memory growth: {e}")
        return False


def get_system_compute_resources(include_gpu: bool = True) -> Dict[str, Any]:
    """
    Get comprehensive system compute resources (CPU + GPU).

    Extends the psutil-based CPU/RAM detection with GPU information.

    Args:
        include_gpu: If True, include GPU detection in results.

    Returns:
        Dict with system resources:
            {
                "cpu_physical_cores": int,
                "cpu_logical_cores": int,
                "ram_total_gb": float,
                "ram_available_gb": float,
                "gpu": Optional[Dict]  # GPU info from detect_gpu_config()
            }

    Examples:
        >>> resources = get_system_compute_resources()
        >>> print(f"CPU cores: {resources['cpu_physical_cores']}")
        >>> if resources['gpu']:
        ...     print(f"GPU: {resources['gpu']['device_name']}")
    """
    import psutil

    resources = {
        "cpu_physical_cores": psutil.cpu_count(logical=False) or 1,
        "cpu_logical_cores": psutil.cpu_count(logical=True) or 1,
        "ram_total_gb": psutil.virtual_memory().total / 1e9,
        "ram_available_gb": psutil.virtual_memory().available / 1e9,
    }

    if include_gpu:
        gpu_info = detect_gpu_config()
        if gpu_info:
            resources["gpu"] = gpu_info
        else:
            resources["gpu"] = None

    return resources


def print_compute_summary(resources: Optional[Dict[str, Any]] = None):
    """
    Print a human-readable summary of available compute resources.

    Args:
        resources: Resource dict from get_system_compute_resources().
                  If None, will detect resources automatically.

    Examples:
        >>> from geo_tda.utils.gpu_detection import print_compute_summary
        >>> print_compute_summary()
        === Compute Resources ===
        CPU: 16 physical cores (32 logical)
        RAM: 64.0 GB total, 48.2 GB available
        GPU: NVIDIA GeForce RTX 4090 (24.0 GB VRAM)
             CUDA 12.1, Compute Capability 8.9
    """
    if resources is None:
        resources = get_system_compute_resources()

    print("=" * 60)
    print("Compute Resources")
    print("=" * 60)
    print(f"CPU: {resources['cpu_physical_cores']} physical cores "
          f"({resources['cpu_logical_cores']} logical)")
    print(f"RAM: {resources['ram_total_gb']:.1f} GB total, "
          f"{resources['ram_available_gb']:.1f} GB available")

    if resources.get("gpu"):
        gpu = resources["gpu"]
        print(f"GPU: {gpu['device_name']} ({gpu['memory_gb']:.1f} GB VRAM)")
        if gpu.get("memory_available_gb"):
            print(f"     {gpu['memory_available_gb']:.1f} GB VRAM available")
        print(f"     CUDA {gpu['cuda_version']}, "
              f"Compute Capability {gpu['compute_capability'][0]}.{gpu['compute_capability'][1]}")
    else:
        print("GPU: Not available (CPU-only mode)")

    print("=" * 60)


# Example usage in notebooks
if __name__ == "__main__":
    # This code runs when the module is executed directly
    # Useful for quick testing: python -m geo_tda.utils.gpu_detection

    import logging
    logging.basicConfig(level=logging.INFO)

    print_compute_summary()

    # Test CuPy availability
    if check_cupy_available():
        print("\nCuPy is available for GPU-accelerated array operations")
    else:
        print("\nCuPy not available (install with: conda install cupy)")

    # Show optimal memory allocation
    gpu = detect_gpu_config()
    if gpu:
        memory_limit = get_optimal_gpu_memory_fraction(gpu)
        print(f"\nRecommended GPU memory limit: {memory_limit / 1e9:.1f} GB "
              f"(80% of {gpu['memory_gb']:.1f} GB total)")
