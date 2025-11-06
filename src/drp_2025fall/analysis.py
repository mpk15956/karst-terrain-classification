"""
Homology computation for simplicial complexes.

This module computes topological invariants (Euler characteristic, Betti numbers)
for abstract simplicial complexes over the field Z/2Z.
"""

from collections import defaultdict
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


from .topology import SimplicialComplex


def compute_euler_characteristic(complex: SimplicialComplex) -> int:
    """
    Compute the Euler characteristic χ of a simplicial complex.

    The Euler characteristic is the alternating sum: χ = k₀ - k₁ + k₂ - k₃ + ...
    where kᵢ is the number of i-simplices.

    :param complex: A simplicial complex.
    :return: The Euler characteristic (integer).
    """
    if not complex.simplices:
        return 0

    # Count simplices by dimension
    counts = defaultdict(int)
    for simplex in complex.simplices:
        dim = len(simplex) - 1
        if dim >= 0:
            counts[dim] += 1

    # Compute alternating sum
    max_dim = max(counts.keys())
    return sum((-1) ** dim * counts.get(dim, 0) for dim in range(max_dim + 1))


def _get_simplices_by_dimension(complex: SimplicialComplex) -> Dict[int, List[Tuple[int, ...]]]:
    """
    Group simplices by dimension and sort them for consistent indexing.

    :param complex: A simplicial complex.
    :return: Dictionary mapping dimension to sorted list of simplices.
    """
    simplices_by_dim = defaultdict(list)

    for simplex in complex.simplices:
        dim = len(simplex) - 1
        if dim >= 0:
            simplices_by_dim[dim].append(simplex)

    # Sort simplices for consistent ordering
    for dim in simplices_by_dim:
        simplices_by_dim[dim].sort()

    return simplices_by_dim


def _compute_boundary_matrix(k: int, simplices_by_dim: Dict[int, List[Tuple[int, ...]]]) -> np.ndarray:
    """
    Compute the boundary matrix ∂ₖ: Cₖ → Cₖ₋₁ over Z/2Z.

    The boundary matrix has rows indexed by (k-1)-simplices and columns indexed
    by k-simplices. Entry (i,j) is 1 if the i-th (k-1)-simplex is a face of
    the j-th k-simplex, and 0 otherwise.

    Over Z/2Z, we don't need to worry about orientation signs.

    :param k: Dimension of the domain chain group.
    :param simplices_by_dim: Dictionary of simplices grouped by dimension.
    :return: Boundary matrix as a numpy array (mod 2).
    """
    k_simplices = simplices_by_dim.get(k, [])
    k_minus_1_simplices = simplices_by_dim.get(k - 1, [])

    if not k_simplices or not k_minus_1_simplices:
        return np.array([[]]).reshape(0, 0)

    num_rows = len(k_minus_1_simplices)
    num_cols = len(k_simplices)

    # Create index map for fast lookup
    simplex_to_index = {simplex: idx for idx, simplex in enumerate(k_minus_1_simplices)}

    # Initialize matrix over Z/2Z (dtype=int for mod operations)
    boundary_matrix = np.zeros((num_rows, num_cols), dtype=int)

    # Fill in the boundary matrix
    for col_idx, k_simplex in enumerate(k_simplices):
        # Compute all (k-1)-faces by removing each vertex
        # Since simplices are sorted tuples, this gives consistent ordering
        for i in range(len(k_simplex)):
            # Remove i-th vertex to get a face
            face = k_simplex[:i] + k_simplex[i+1:]

            if face in simplex_to_index:
                row_idx = simplex_to_index[face]
                # Over Z/2Z: 1 + 1 = 0, so we XOR (toggle) the entry
                boundary_matrix[row_idx, col_idx] = (boundary_matrix[row_idx, col_idx] + 1) % 2

    return boundary_matrix


def _matrix_rank_mod2(matrix: np.ndarray) -> int:
    """
    Compute the rank of a matrix over Z/2Z using Gaussian elimination.

    :param matrix: A numpy array with integer entries.
    :return: The rank of the matrix over Z/2Z.
    """
    if matrix.size == 0:
        return 0

    # Work with a copy to avoid modifying the original
    m = matrix.copy() % 2
    num_rows, num_cols = m.shape

    rank = 0
    pivot_row = 0

    for col in range(num_cols):
        if pivot_row >= num_rows:
            break

        # Find a pivot in this column
        pivot_found = False
        for row in range(pivot_row, num_rows):
            if m[row, col] == 1:
                # Swap rows
                m[[pivot_row, row]] = m[[row, pivot_row]]
                pivot_found = True
                break

        if not pivot_found:
            continue

        # Eliminate all other 1s in this column (over Z/2Z, just XOR)
        for row in range(num_rows):
            if row != pivot_row and m[row, col] == 1:
                m[row] = (m[row] + m[pivot_row]) % 2

        rank += 1
        pivot_row += 1

    return rank


def compute_betti_numbers(complex: SimplicialComplex) -> Dict[int, int]:
    """
    Compute the Betti numbers βₖ of a simplicial complex over Z/2Z.

    The k-th Betti number is: βₖ = dim(ker ∂ₖ) - dim(im ∂ₖ₊₁)
    where ∂ₖ is the k-th boundary operator.

    Interpretation:
    - β₀ = number of connected components
    - β₁ = number of 1-dimensional holes (loops)
    - β₂ = number of 2-dimensional voids (cavities)

    :param complex: A simplicial complex.
    :return: Dictionary mapping dimension k to the k-th Betti number.
    """
    simplices_by_dim = _get_simplices_by_dimension(complex)

    if not simplices_by_dim:
        return {0: 0}

    max_dim = max(simplices_by_dim.keys())
    betti_numbers = {}

    # Compute boundary matrices and their ranks
    ranks = {}
    for k in range(1, max_dim + 2):
        boundary_matrix = _compute_boundary_matrix(k, simplices_by_dim)
        ranks[k] = _matrix_rank_mod2(boundary_matrix)

    # Compute Betti numbers using rank-nullity theorem
    # β₀ = dim(ker ∂₀) - dim(im ∂₁)
    # Since ∂₀: C₀ → C₋₁ = 0, ker(∂₀) = C₀, so dim(ker ∂₀) = number of vertices
    num_vertices = len(simplices_by_dim.get(0, []))
    betti_numbers[0] = num_vertices - ranks.get(1, 0)

    # For k ≥ 1: βₖ = dim(ker ∂ₖ) - dim(im ∂ₖ₊₁)
    # dim(ker ∂ₖ) = dim(Cₖ) - rank(∂ₖ)
    for k in range(1, max_dim + 1):
        num_k_simplices = len(simplices_by_dim.get(k, []))
        dim_ker_dk = num_k_simplices - ranks.get(k, 0)
        dim_im_dk_plus_1 = ranks.get(k + 1, 0)
        betti_numbers[k] = dim_ker_dk - dim_im_dk_plus_1

    return betti_numbers


def plot_histogram(data: pd.Series, num_vertices: int, num_runs: int,
                   figsize: tuple = (10, 6)) -> None:
    """
    Create histogram of Euler characteristic distribution.
    
    Args:
        data: Series containing Euler characteristic values
        num_vertices: Number of vertices in the complexes
        num_runs: Number of simulation runs
        figsize: Figure size tuple (width, height)
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Create histogram with integer bins
    bins = range(int(data.min()) - 1, int(data.max()) + 2)
    ax.hist(
        data, 
        bins=bins,
        edgecolor='black',
        alpha=0.7,
        color=sns.color_palette("colorblind")[0]
    )
    
    # Add mean and median lines
    mean_val = data.mean()
    median_val = data.median()
    
    ax.axvline(
        mean_val, 
        color='red', 
        linestyle='--', 
        linewidth=2,
        label=f'Mean = {mean_val:.2f}'
    )
    ax.axvline(
        median_val, 
        color='green', 
        linestyle='--', 
        linewidth=2,
        label=f'Median = {median_val:.0f}'
    )
    
    ax.set_xlabel('Euler Characteristic (χ)', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title(
        f'Distribution of Euler Characteristics\n({num_runs} Random Complexes, {num_vertices} Vertices)',
        fontsize=14,
        fontweight='bold'
    )
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.show()


def plot_boxplot(data: pd.Series, num_vertices: int, num_runs: int,
                 figsize: tuple = (8, 6)) -> None:
    """
    Create box plot of Euler characteristic distribution.
    
    Args:
        data: Series containing Euler characteristic values
        num_vertices: Number of vertices in the complexes
        num_runs: Number of simulation runs
        figsize: Figure size tuple (width, height)
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Create box plot
    box_parts = ax.boxplot(
        [data],
        vert=True,
        patch_artist=True,
        tick_labels=['Euler Characteristic'],
        widths=0.5
    )
    
    # Customize colors
    for patch in box_parts['boxes']:
        patch.set_facecolor(sns.color_palette("colorblind")[1])
        patch.set_alpha(0.7)
    
    for whisker in box_parts['whiskers']:
        whisker.set(linewidth=1.5)
    
    for cap in box_parts['caps']:
        cap.set(linewidth=1.5)
    
    for median in box_parts['medians']:
        median.set(color='red', linewidth=2)
    
    # Add mean as a point
    mean_val = data.mean()
    ax.plot([1], [mean_val], 'D', color='green', markersize=10, 
            label=f'Mean = {mean_val:.2f}', zorder=3)
    
    # Add quartile annotations
    q1, q2, q3 = data.quantile([0.25, 0.5, 0.75])
    ax.text(1.15, q3, f'Q3 = {q3:.1f}', verticalalignment='center', fontsize=10)
    ax.text(1.15, q2, f'Median = {q2:.1f}', verticalalignment='center', 
            fontsize=10, color='red')
    ax.text(1.15, q1, f'Q1 = {q1:.1f}', verticalalignment='center', fontsize=10)
    
    ax.set_ylabel('Euler Characteristic (χ)', fontsize=12)
    ax.set_title(
        f'Box Plot of Euler Characteristics\n({num_runs} Random Complexes, {num_vertices} Vertices)',
        fontsize=14,
        fontweight='bold'
    )
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.show()


def plot_combined_visualization(data: pd.Series, num_vertices: int, num_runs: int) -> None:
    """
    Create side-by-side histogram and box plot.

    Args:
        data: Series containing Euler characteristic values
        num_vertices: Number of vertices in the complexes
        num_runs: Number of simulation runs
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Histogram on the left
    bins = range(int(data.min()) - 1, int(data.max()) + 2)
    ax1.hist(
        data,
        bins=bins,
        edgecolor='black',
        alpha=0.7,
        color=sns.color_palette("colorblind")[0]
    )

    mean_val = data.mean()
    median_val = data.median()

    ax1.axvline(mean_val, color='red', linestyle='--', linewidth=2,
                label=f'Mean = {mean_val:.2f}')
    ax1.axvline(median_val, color='green', linestyle='--', linewidth=2,
                label=f'Median = {median_val:.0f}')
    ax1.set_xlabel('Euler Characteristic (χ)', fontsize=12)
    ax1.set_ylabel('Frequency', fontsize=12)
    ax1.set_title('Histogram', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(axis='y', alpha=0.3)

    # Box plot on the right
    box_parts = ax2.boxplot(
        [data],
        vert=True,
        patch_artist=True,
        tick_labels=[''],
        widths=0.5
    )

    for patch in box_parts['boxes']:
        patch.set_facecolor(sns.color_palette("colorblind")[1])
        patch.set_alpha(0.7)

    for median in box_parts['medians']:
        median.set(color='red', linewidth=2)

    ax2.plot([1], [mean_val], 'D', color='green', markersize=10,
             label=f'Mean = {mean_val:.2f}', zorder=3)
    ax2.set_ylabel('Euler Characteristic (χ)', fontsize=12)
    ax2.set_title('Box Plot', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(axis='y', alpha=0.3)

    fig.suptitle(
        f'Euler Characteristic Distribution: {num_runs} Random Complexes ({num_vertices} Vertices)',
        fontsize=15,
        fontweight='bold',
        y=1.02
    )

    plt.tight_layout()
    plt.show()


def plot_betti_distributions(dataframe: pd.DataFrame, num_runs: int) -> None:
    """
    Create histogram distributions for all Betti numbers.

    Args:
        dataframe: DataFrame containing Betti number results (columns = β₀, β₁, β₂, ...)
        num_runs: Number of simulation runs (for plot title)

    Example:
        df = pd.DataFrame({0: [1, 1, 2], 1: [3, 4, 5]})
        plot_betti_distributions(df, 100)
    """
    from matplotlib.ticker import MaxNLocator

    sorted_cols = sorted(dataframe.columns)
    num_betti = len(sorted_cols)

    if num_betti == 0:
        print("No Betti numbers to plot.")
        return

    # Determine grid layout (e.g., max 3 columns)
    ncols = min(num_betti, 3)
    nrows = (num_betti + ncols - 1) // ncols  # Ceiling division

    fig, axes = plt.subplots(
        nrows, ncols, figsize=(5 * ncols, 4 * nrows), sharey=True, squeeze=False
    )
    axes_flat = axes.flatten()

    fig.suptitle(
        f'Distribution of Betti Numbers over {num_runs} Runs',
        fontsize=16,
        fontweight='bold'
    )

    for i, col in enumerate(sorted_cols):
        ax = axes_flat[i]
        sns.histplot(
            data=dataframe,
            x=col,
            ax=ax,
            discrete=True,
            stat="density",
            kde=False,
            color=sns.color_palette("colorblind")[i % 10]
        )
        ax.set_title(f'$\\beta_{{{col}}}$', fontsize=14, fontweight='bold')
        ax.set_xlabel('Betti Number', fontsize=12)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(axis='y', linestyle='--', alpha=0.7)

    # Hide any unused subplots
    for i in range(num_betti, len(axes_flat)):
        axes_flat[i].set_visible(False)

    # Set shared y-label
    for ax_row in axes:
        ax_row[0].set_ylabel('Density', fontsize=12)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()
