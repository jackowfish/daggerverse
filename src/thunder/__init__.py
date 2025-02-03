"""Thunder Compute module for running GPU workloads

This module provides integration with Thunder Compute for running workloads on GPU-enabled Kubernetes nodes.
"""

from .main import deploy, destroy

__all__ = ["deploy", "destroy"]
