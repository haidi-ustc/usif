#!/usr/bin/env python3
"""
Thread Safety Tests for USIF StructureContainer
Tests concurrent access and index operations
"""

import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from usif import (
    CompressionType,
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
    WyckoffSite,
)
from usif.storage import StructureContainer


class TestContainerThreadSafety(unittest.TestCase):
    """Test thread safety of StructureContainer"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".usifc")
        self.temp_path = self.temp_file.name
        self.temp_file.close()

    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_path):
            os.unlink(self.temp_path)

    def _create_test_structure(
        self, element: int = 14, energy: float = -10.0
    ) -> USIFStructure:
        """Create a test structure"""
        return USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(element, 8, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(energy=energy),
            formula=f"Element{element}",
        )

    def test_concurrent_add_operations(self):
        """Test concurrent additions to container"""
        num_threads = 10
        structures_per_thread = 5

        with StructureContainer(self.temp_path, mode="w") as container:

            def add_structures(thread_id: int):
                """Add structures from a thread"""
                hashes = []
                for i in range(structures_per_thread):
                    structure = self._create_test_structure(
                        element=14 + thread_id * 10 + i,
                        energy=-10.0 - thread_id - i * 0.1,
                    )
                    name = f"structure_t{thread_id}_s{i}"
                    hash_val = container.add(structure, name=name)
                    hashes.append(hash_val)
                return hashes

            # Execute concurrent additions
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [
                    executor.submit(add_structures, i) for i in range(num_threads)
                ]
                all_hashes = []
                for future in as_completed(futures):
                    hashes = future.result()
                    all_hashes.extend(hashes)

            # Verify all structures were added
            self.assertEqual(len(all_hashes), num_threads * structures_per_thread)
            self.assertEqual(len(set(all_hashes)), len(all_hashes))  # All unique

            # Verify we can retrieve all structures
            for hash_val in all_hashes:
                structure = container.get(hash_val)
                self.assertIsNotNone(structure)

    def test_concurrent_read_operations(self):
        """Test concurrent reads from container"""
        num_structures = 20
        num_readers = 10
        reads_per_thread = 50

        # First, populate container
        with StructureContainer(self.temp_path, mode="w") as container:
            hashes = []
            for i in range(num_structures):
                structure = self._create_test_structure(
                    element=14 + i, energy=-10.0 - i
                )
                name = f"structure_{i}"
                hash_val = container.add(structure, name=name)
                hashes.append(hash_val)

        # Now test concurrent reads
        with StructureContainer(self.temp_path, mode="r") as container:
            successful_reads = [0] * num_readers
            errors = [[] for _ in range(num_readers)]

            def read_structures(thread_id: int):
                """Read structures from a thread"""
                import random

                for _ in range(reads_per_thread):
                    try:
                        # Randomly pick a structure to read
                        hash_val = random.choice(hashes)
                        structure = container.get(hash_val)
                        if structure is not None:
                            successful_reads[thread_id] += 1
                    except Exception as e:
                        errors[thread_id].append(str(e))

            # Execute concurrent reads
            with ThreadPoolExecutor(max_workers=num_readers) as executor:
                futures = [
                    executor.submit(read_structures, i) for i in range(num_readers)
                ]
                for future in as_completed(futures):
                    future.result()

            # Verify all reads were successful
            total_reads = sum(successful_reads)
            self.assertEqual(total_reads, num_readers * reads_per_thread)

            # Verify no errors
            all_errors = [e for thread_errors in errors for e in thread_errors]
            self.assertEqual(len(all_errors), 0, f"Errors occurred: {all_errors}")

    def test_concurrent_query_operations(self):
        """Test concurrent query operations"""
        num_structures = 50
        num_queriers = 5
        queries_per_thread = 20

        # Populate container with varied structures
        with StructureContainer(self.temp_path, mode="w") as container:
            for i in range(num_structures):
                structure = self._create_test_structure(
                    element=14 + (i % 5), energy=-10.0 - (i % 10)
                )
                container.add(structure, name=f"structure_{i}")

        # Test concurrent queries
        with StructureContainer(self.temp_path, mode="r") as container:
            query_results = [[] for _ in range(num_queriers)]

            def query_structures(thread_id: int):
                """Query structures from a thread"""
                for i in range(queries_per_thread):
                    # Alternate between different query types
                    if i % 3 == 0:
                        results = container.query(formula=f"Element{14 + (i % 5)}")
                    elif i % 3 == 1:
                        results = container.query(energy_range=(-15.0, -5.0))
                    else:
                        results = container.query()  # Get all
                    query_results[thread_id].append(len(results))

            # Execute concurrent queries
            with ThreadPoolExecutor(max_workers=num_queriers) as executor:
                futures = [
                    executor.submit(query_structures, i) for i in range(num_queriers)
                ]
                for future in as_completed(futures):
                    future.result()

            # Verify all queries completed
            for results in query_results:
                self.assertEqual(len(results), queries_per_thread)

    def test_mixed_concurrent_operations(self):
        """Test mixed read/write operations (requires append mode)"""
        num_initial = 10
        num_writers = 3
        num_readers = 5
        operations_per_thread = 10

        # Create initial container
        with StructureContainer(self.temp_path, mode="w") as container:
            initial_hashes = []
            for i in range(num_initial):
                structure = self._create_test_structure(
                    element=14 + i, energy=-10.0 - i
                )
                hash_val = container.add(structure, name=f"initial_{i}")
                initial_hashes.append(hash_val)

        # Test mixed operations in append mode
        with StructureContainer(self.temp_path, mode="a") as container:
            write_counts = [0] * num_writers
            read_counts = [0] * num_readers

            def write_operations(thread_id: int):
                """Write structures"""
                for i in range(operations_per_thread):
                    structure = self._create_test_structure(
                        element=100 + thread_id * 10 + i,
                        energy=-20.0 - thread_id - i * 0.1,
                    )
                    name = f"added_t{thread_id}_s{i}"
                    container.add(structure, name=name)
                    write_counts[thread_id] += 1
                    time.sleep(0.001)  # Small delay to increase contention

            def read_operations(thread_id: int):
                """Read structures"""
                import random

                for _ in range(operations_per_thread):
                    if initial_hashes:
                        hash_val = random.choice(initial_hashes)
                        structure = container.get(hash_val)
                        if structure is not None:
                            read_counts[thread_id] += 1
                    time.sleep(0.001)

            # Execute mixed operations
            with ThreadPoolExecutor(max_workers=num_writers + num_readers) as executor:
                write_futures = [
                    executor.submit(write_operations, i) for i in range(num_writers)
                ]
                read_futures = [
                    executor.submit(read_operations, i) for i in range(num_readers)
                ]

                for future in as_completed(write_futures + read_futures):
                    future.result()

            # Verify operations completed
            self.assertEqual(sum(write_counts), num_writers * operations_per_thread)
            self.assertGreater(sum(read_counts), 0)  # At least some reads succeeded

    def test_secondary_index_consistency(self):
        """Test that secondary indexes are consistent after concurrent additions"""
        num_structures = 100

        with StructureContainer(self.temp_path, mode="w") as container:
            # Add structures concurrently
            def add_batch(start_idx: int, count: int):
                """Add a batch of structures"""
                for i in range(count):
                    idx = start_idx + i
                    structure = self._create_test_structure(
                        element=14 + (idx % 10), energy=-10.0 - (idx % 5)
                    )
                    container.add(structure, name=f"structure_{idx}")

            batch_size = 20
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for i in range(0, num_structures, batch_size):
                    futures.append(executor.submit(add_batch, i, batch_size))

                for future in as_completed(futures):
                    future.result()

            # Verify secondary indexes are consistent
            # Query by formula should work correctly
            for element in range(14, 24):
                formula = f"Element{element}"
                results = container.query(formula=formula)
                # Should have roughly num_structures / 10 results
                self.assertGreater(len(results), 0)

    def test_no_race_condition_in_duplicate_detection(self):
        """Test that duplicate detection works correctly under concurrent access"""
        # Create a structure
        structure = self._create_test_structure(element=14, energy=-10.0)

        with StructureContainer(self.temp_path, mode="w") as container:
            # Try to add the same structure from multiple threads
            num_threads = 10
            hashes = [None] * num_threads

            def add_same_structure(thread_id: int):
                """Try to add the same structure"""
                hash_val = container.add(structure, name=f"attempt_{thread_id}")
                hashes[thread_id] = hash_val

            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [
                    executor.submit(add_same_structure, i) for i in range(num_threads)
                ]
                for future in as_completed(futures):
                    future.result()

            # All hashes should be the same (same structure)
            unique_hashes = set(hashes)
            self.assertEqual(
                len(unique_hashes),
                1,
                f"Expected 1 unique hash, got {len(unique_hashes)}: {unique_hashes}",
            )


if __name__ == "__main__":
    unittest.main()
