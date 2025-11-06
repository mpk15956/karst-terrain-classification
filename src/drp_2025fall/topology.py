"""
Simplicial complex implementation for topological data analysis.

This module provides a combinatorial representation of abstract simplicial complexes,
where simplices are represented as tuples of vertex indices (integers).
"""

import itertools
import random
from typing import Set, Iterable, Tuple


class SimplicialComplex:
    """
    Represents an abstract simplicial complex.

    A simplicial complex is a downward-closed collection of simplices.
    Each simplex is represented as a tuple of sorted integer vertex indices.
    Using tuples (instead of frozensets) ensures consistent vertex ordering
    for boundary operator computations.
    """

    def __init__(self, simplices: Set[Tuple[int, ...]]):
        """
        Initialize a simplicial complex from a set of simplices.

        :param simplices: Set of tuples representing simplices. Each tuple
                         should contain sorted vertex indices.
        :raises ValueError: If the complex is not downward-closed.
        """
        # Ensure all simplices are sorted tuples
        self._simplices = {tuple(sorted(s)) for s in simplices}

        if not self._is_valid():
            raise ValueError(
                "The provided set of simplices is not downward-closed. "
                "All faces of each simplex must be present in the complex."
            )

    def _is_valid(self) -> bool:
        """Check if the complex is downward-closed (all faces present)."""
        for simplex in self._simplices:
            if len(simplex) > 1:
                # Check all (k-1)-faces exist
                for i in range(len(simplex)):
                    face = simplex[:i] + simplex[i+1:]
                    if face not in self._simplices:
                        return False
        return True

    @classmethod
    def from_maximal_simplices(cls, maximal_simplices: Iterable[Iterable[int]]) -> 'SimplicialComplex':
        """
        Create a complex from its maximal simplices (facets).

        Automatically generates all faces of the maximal simplices.

        :param maximal_simplices: Iterable of vertex collections.
        :return: A valid simplicial complex.
        """
        all_simplices = set()

        for maximal_simplex in maximal_simplices:
            vertices = sorted(set(maximal_simplex))
            if not vertices:
                continue

            # Generate all faces (including the maximal simplex itself)
            for k in range(1, len(vertices) + 1):
                for face in itertools.combinations(vertices, k):
                    all_simplices.add(face)

        return cls(all_simplices)

    @classmethod
    def from_bottom_up_process(cls, num_vertices: int, p_dict: dict[int, float]) -> 'SimplicialComplex':
        """
        Create a random complex using a bottom-up probabilistic process.

        Simplices at each dimension are added with probability p_dict[k],
        but only if all their boundary faces are already present.

        This implementation uses efficient set lookups and early bailout
        for improved performance on larger complexes.

        :param num_vertices: Number of vertices (labeled 0 to num_vertices-1).
        :param p_dict: Dictionary mapping dimension k to probability p_k.
        :return: A randomly generated simplicial complex.
        """
        # Start with all vertices (0-simplices)
        simplices = {(i,) for i in range(num_vertices)}

        # Add higher-dimensional simplices probabilistically
        for k in range(1, num_vertices):
            pk = p_dict.get(k, 0.0)
            if pk == 0:
                continue

            # Consider all possible k-simplices
            for candidate_tuple in itertools.combinations(range(num_vertices), k + 1):
                candidate = tuple(candidate_tuple)  # Already sorted

                # Check if all (k-1)-faces are present (optimized with early exit)
                # Using all() with generator for better performance
                faces = (candidate[:i] + candidate[i+1:] for i in range(len(candidate)))
                boundary_present = all(face in simplices for face in faces)

                # Add with probability pk if boundary exists
                if boundary_present and random.random() < pk:
                    simplices.add(candidate)

        return cls(simplices)

    @classmethod
    def from_top_down_process(cls, num_vertices: int, p_keep: float) -> 'SimplicialComplex':
        """
        Create a random complex using a top-down erosion process.

        Starts with the full (n-1)-simplex and probabilistically removes faces.

        :param num_vertices: Number of vertices.
        :param p_keep: Probability of keeping a face at each level.
        :return: A randomly generated simplicial complex.
        """
        if not (0 <= p_keep <= 1):
            raise ValueError("p_keep must be between 0 and 1.")

        current_maximals = {tuple(range(num_vertices))}

        # Erode from top dimension down
        for dim in range(num_vertices - 1, 0, -1):
            next_maximals = set()
            faces_to_consider = set()

            # Generate all dim-faces from current maximals
            for simplex in current_maximals:
                for face in itertools.combinations(simplex, dim):
                    faces_to_consider.add(face)

            # Keep each face with probability p_keep
            for face in faces_to_consider:
                if random.random() < p_keep:
                    next_maximals.add(face)

            if not next_maximals:
                current_maximals = set()
                break

            current_maximals = next_maximals

        return cls.from_maximal_simplices(current_maximals)

    @property
    def simplices(self) -> Set[Tuple[int, ...]]:
        """Return the set of all simplices in the complex."""
        return self._simplices

    @property
    def dimension(self) -> int:
        """Return the dimension of the complex (highest simplex dimension)."""
        if not self.simplices:
            return -1
        return max(len(s) - 1 for s in self.simplices)

    def __repr__(self) -> str:
        """String representation of the complex."""
        if not self.simplices:
            return "SimplicialComplex(vertices=0, simplices=0, dim=-1)"

        all_vertices = set()
        for simplex in self.simplices:
            all_vertices.update(simplex)

        num_vertices = len(all_vertices)
        num_simplices = len(self.simplices)

        return f"SimplicialComplex(vertices={num_vertices}, simplices={num_simplices}, dim={self.dimension})"