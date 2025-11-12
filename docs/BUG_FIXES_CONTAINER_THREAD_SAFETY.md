# Container Thread Safety Bug Fixes

## Overview
Fixed critical thread safety issues and secondary index limitation in `usif/container.py` as identified in the code review.

## Issues Fixed

### 1. Thread Safety Vulnerabilities (Critical)

**Problem**: Multiple concurrent threads could corrupt container state due to unprotected access to shared data structures.

**Affected Areas**:
- `_hash_index`: Structure hash to location mapping
- `_name_index`: Name to hash mapping  
- `_formula_index`: Formula-based secondary index
- `_property_index`: Property-based secondary index
- File I/O operations (seek/read/write)

**Solution**:
- Added `_index_lock` (threading.RLock) to protect all index operations
- Added `_file_lock` (threading.RLock) to protect all file I/O operations
- Wrapped all index read/write operations with appropriate locks
- Protected file operations in `add()`, `get()`, `_read_from_chunk()`, `_write_to_chunk()`, `_allocate_space()`
- Made `_write_enhanced_index()` thread-safe

**Changes**:
```python
# Added locks
self._index_lock = threading.RLock()
self._file_lock = threading.RLock()

# Protected operations
with self._index_lock:
    # Index operations
    
with self._file_lock:
    # File I/O operations
```

### 2. Secondary Index Limitation (High Priority)

**Problem**: `_build_secondary_indexes()` only indexed first 10 structures due to hard-coded slice `[:10]`, making queries ineffective for larger containers.

**Solution**:
- Removed the 10-structure limitation
- Now indexes all structures in the container
- Added progress logging for large containers (every 100 structures)
- Made index building thread-safe with `_index_lock`

**Before**:
```python
for struct_hash in list(self._hash_index.keys())[:10]:  # Only 10!
    # Index structure
```

**After**:
```python
all_hashes = list(self._hash_index.keys())
total = len(all_hashes)

with self._index_lock:
    for i, struct_hash in enumerate(all_hashes):
        # Index all structures
        if (i + 1) % 100 == 0:
            logger.info(f"Indexed {i + 1}/{total} structures...")
```

### 3. Index Serialization/Deserialization Mismatch (Critical)

**Problem**: `_read_enhanced_index()` used an old format expecting fixed 32-byte hashes, but `_serialize_indexes()` wrote variable-length hash strings. This caused indexes to not persist/load correctly.

**Solution**:
- Implemented `_deserialize_indexes()` to match `_serialize_indexes()` format exactly
- Added `_deserialize_group_hierarchy()` to properly load group data
- Fixed `_write_enhanced_index()` to seek to end of file before writing
- Made serialization/deserialization thread-safe

**Format** (now consistent):
- Hash index: count, then for each: hash_len, hash_bytes, chunk_id, offset, size
- Name index: count, then for each: name_len, name_bytes, hash_len, hash_bytes
- Structure attributes: count, then nested name/value pairs
- Group hierarchy: recursive serialization of group tree

### 4. File Position Management (Medium Priority)

**Problem**: `_write_enhanced_index()` used `tell()` without seeking to end, potentially writing index at wrong location.

**Solution**:
```python
self._file.seek(0, 2)  # Seek to end first
index_offset = self._file.tell()
self._file.write(index_data)
```

## Testing

Created comprehensive thread safety test suite (`tests/test_container_threadsafety.py`):

1. **test_concurrent_add_operations**: 10 threads adding 5 structures each simultaneously
2. **test_concurrent_read_operations**: 10 threads reading 50 times each from 20 structures  
3. **test_concurrent_query_operations**: 5 threads performing 20 queries each
4. **test_mixed_concurrent_operations**: 3 writers + 5 readers operating simultaneously
5. **test_secondary_index_consistency**: Verify indexes remain consistent with concurrent adds
6. **test_no_race_condition_in_duplicate_detection**: Verify duplicate detection under concurrency

**All tests pass** ✓

## Performance Impact

- **Locking overhead**: Minimal - RLocks are only held during critical sections
- **Index building**: Now indexes all structures (not just 10), may take longer for large containers but provides correct functionality
- **Progress logging**: Added every 100 structures to track progress on large containers
- **Thread safety**: Enables safe concurrent access, crucial for multi-threaded applications

## Backward Compatibility

- All existing container tests pass ✓
- New serialization format is used for new/updated containers
- File format version unchanged (v1)
- API unchanged - all fixes are internal

## Migration Notes

Containers created before this fix will need to be rebuilt to benefit from:
1. Full secondary indexing (not just first 10 structures)
2. New serialization format for proper index persistence

To rebuild a container:
```python
# Read structures from old container
old_container = StructureContainer("old.usifc", mode='r')
structures = list(old_container)

# Write to new container
with StructureContainer("new.usifc", mode='w') as new_container:
    for hash_val, structure in structures:
        new_container.add(structure)
```

## Code Review Compliance

This fix addresses the following items from `CODE_REVIEW_2025.md`:

- ✅ **Issue 1**: Thread safety gaps in container (CRITICAL)
- ✅ **Issue 2**: Secondary index 10-element limit (HIGH)
- ✅ **Issue 3**: Index serialization/deserialization mismatch (CRITICAL)
- ✅ **Issue 4**: File position management (MEDIUM)

## Files Modified

1. `usif/container.py`:
   - Added `_index_lock` and `_file_lock`
   - Protected all index operations with `_index_lock`
   - Protected all file I/O with `_file_lock`
   - Removed 10-structure limit in `_build_secondary_indexes()`
   - Added `_deserialize_indexes()` method
   - Added `_deserialize_group_hierarchy()` method
   - Fixed `_write_enhanced_index()` file seeking

2. `tests/test_container_threadsafety.py`:
   - New comprehensive thread safety test suite (6 tests)

3. `docs/BUG_FIXES_CONTAINER_THREAD_SAFETY.md`:
   - This documentation file

## Verification

```bash
# Run thread safety tests
pytest tests/test_container_threadsafety.py -v

# Run all container tests
pytest tests/test_container.py -v

# Run full test suite
pytest tests/ -v
```

All tests pass successfully.

---

**Date**: 2025-11-12
**Author**: AI Code Review & Fix
**Status**: ✅ Complete and Tested

