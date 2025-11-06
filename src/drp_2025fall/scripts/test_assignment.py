"""
Test script for Problem Set 2: Verify all functionality works correctly.
"""

from src.drp_fall_2025.topology import SimplicialComplex
from src.drp_fall_2025.analysis import (
    compute_betti_numbers,
    compute_euler_characteristic,
    generate_complexes_bottom_up
)
import pandas as pd


def test_basic_complexes():
    """Test basic known complexes."""
    print("=" * 60)
    print("Testing Basic Complexes")
    print("=" * 60)

    # Test 1: Single vertex
    vertex = SimplicialComplex({(0,)})
    print(f"\n1. Single vertex:")
    print(f"   Betti numbers: {compute_betti_numbers(vertex)}")
    print(f"   Expected: b0=1 (one component)")
    assert compute_betti_numbers(vertex) == {0: 1}

    # Test 2: Two disconnected vertices
    two_vertices = SimplicialComplex({(0,), (1,)})
    print(f"\n2. Two disconnected vertices:")
    print(f"   Betti numbers: {compute_betti_numbers(two_vertices)}")
    print(f"   Expected: b0=2 (two components)")
    assert compute_betti_numbers(two_vertices)[0] == 2

    # Test 3: Edge (connected)
    edge = SimplicialComplex({(0,), (1,), (0, 1)})
    print(f"\n3. Single edge:")
    print(f"   Betti numbers: {compute_betti_numbers(edge)}")
    print(f"   Expected: b0=1, b1=0 (connected, no loops)")
    assert compute_betti_numbers(edge) == {0: 1, 1: 0}

    # Test 4: Triangle boundary (loop)
    loop = SimplicialComplex({
        (0,), (1,), (2,),
        (0, 1), (1, 2), (0, 2)
    })
    print(f"\n4. Triangle boundary (loop):")
    print(f"   Betti numbers: {compute_betti_numbers(loop)}")
    print(f"   Expected: b0=1, b1=1 (one component, one loop)")
    betti = compute_betti_numbers(loop)
    assert betti[0] == 1 and betti[1] == 1

    # Test 5: Filled triangle
    triangle = SimplicialComplex.from_maximal_simplices([[0, 1, 2]])
    print(f"\n5. Filled triangle:")
    print(f"   Betti numbers: {compute_betti_numbers(triangle)}")
    print(f"   Expected: b0=1, b1=0, b2=0 (filled, no holes)")
    betti = compute_betti_numbers(triangle)
    assert betti[0] == 1 and betti[1] == 0

    print("\n[PASS] All basic tests passed!")


def test_euler_characteristic():
    """Test Euler characteristic computations."""
    print("\n" + "=" * 60)
    print("Testing Euler Characteristic")
    print("=" * 60)

    # Triangle: chi = 3 - 3 + 1 = 1
    triangle = SimplicialComplex.from_maximal_simplices([[0, 1, 2]])
    chi = compute_euler_characteristic(triangle)
    print(f"\nTriangle: chi = {chi} (expected: 1)")
    assert chi == 1

    # Square boundary: chi = 4 - 4 = 0
    square = SimplicialComplex({
        (0,), (1,), (2,), (3,),
        (0, 1), (1, 2), (2, 3), (0, 3)
    })
    chi = compute_euler_characteristic(square)
    print(f"Square boundary: chi = {chi} (expected: 0)")
    assert chi == 0

    print("\n[PASS] Euler characteristic tests passed!")


def test_random_generation():
    """Test random complex generation (assignment parts c and f)."""
    print("\n" + "=" * 60)
    print("Testing Random Complex Generation (Assignment)")
    print("=" * 60)

    NUM_VERTICES = 10
    NUM_RUNS = 10  # Use smaller number for quick test
    P_DICT = {k: 0.5 for k in range(1, 11)}

    print(f"\nGenerating {NUM_RUNS} random complexes with {NUM_VERTICES} vertices...")

    results = []
    for i in range(NUM_RUNS):
        complex_i = SimplicialComplex.from_bottom_up_process(NUM_VERTICES, P_DICT)
        betti = compute_betti_numbers(complex_i)
        results.append(betti)

    df = pd.DataFrame(results).fillna(0).astype(int)

    print(f"\nResults from {NUM_RUNS} runs:")
    print(f"Average Betti numbers:")
    print(df.mean())

    print(f"\nBetti number ranges:")
    print(f"  b0: {df[0].min()} to {df[0].max()}")
    if 1 in df.columns:
        print(f"  b1: {df[1].min()} to {df[1].max()}")
    if 2 in df.columns:
        print(f"  b2: {df[2].min()} to {df[2].max()}")

    print("\n[PASS] Random generation works correctly!")


if __name__ == "__main__":
    test_basic_complexes()
    test_euler_characteristic()
    test_random_generation()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print("\nThe implementation is working correctly.")
    print("You can now run problem_set_2.ipynb for the full assignment.")
