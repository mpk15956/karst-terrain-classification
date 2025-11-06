"""
Abstract interfaces for topological data structures.

This module provides minimal abstract base classes for simplicial complexes.
These interfaces are optional and mainly serve documentation purposes.
"""

from abc import ABC, abstractmethod
from typing import Set, Tuple


class AbstractSimplicialComplex(ABC):
    """
    Abstract interface for a simplicial complex.

    A simplicial complex is a collection of simplices that is closed under
    taking faces (downward-closed property).
    """

    @property
    @abstractmethod
    def simplices(self) -> Set[Tuple[int, ...]]:
        """
        Return all simplices in the complex.

        Each simplex is represented as a tuple of sorted vertex indices.
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """
        Return the dimension of the complex.

        The dimension is the maximum dimension of any simplex in the complex.
        Returns -1 for an empty complex.
        """
        pass