# USIF Container Format (`.usifc`)

USIF containers store many encoded `.usif` records in one append-friendly file with indexes for lookup and query. Container identity separates `geometry_hash` for geometry lookup and `record_hash` for primary-key deduplication. Enhanced indexes include generation metadata, payload size, CRC32 checksum, and a commit marker so the reader can fall back to the previous valid index generation.
