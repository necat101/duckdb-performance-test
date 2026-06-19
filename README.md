# DuckDB Performance Test

Performance comparison demonstrating the advice from HN discussion:
**"Why DuckDB is my first choice for data processing"**
https://news.ycombinator.com/item?id=46645176

## Key Findings

Based on testing with 10K to 500K row datasets:

| Dataset Size | Python JSON | DuckDB (JSON) | DuckDB (Parquet) | Speedup |
|--------------|-------------|---------------|------------------|---------|
| 10,000 rows | 0.053s | 0.116s | 0.008s | **6.8x** |
| 100,000 rows | 0.514s | 0.334s | 0.014s | **35.8x** |
| 500,000 rows | 3.807s | 0.985s | 0.044s | **86.5x** |

### Storage Efficiency
- JSON: 84.7 MB → Parquet: 10.3 MB (**8.2x smaller**)

## What This Demonstrates

From the HN discussion, key advantages of DuckDB:

1. **Direct File Querying**
   - Query JSON/CSV/Parquet files directly without loading into memory
   - No ETL step needed for exploratory analysis
   - `SELECT * FROM 'data.json'` just works

2. **Optimized Parsers**
   - DuckDB's JSON/CSV readers are highly optimized and parallelized
   - Auto-detects schema and types
   - Even querying raw JSON is faster than Python at scale

3. **Parquet Advantages**
   - Columnar format = only read columns you need
   - Built-in metadata enables predicate pushdown
   - Automatic zone maps (min/max per row group)
   - Excellent compression

4. **"Full scans are fine"**
   - For medium data (< few GB), DuckDB is fast enough that indexing often isn't needed
   - Parallel execution across all CPU cores
   - Vectorized execution engine

5. **Workflow Benefits**
   - Convert to Parquet once: `COPY (SELECT * FROM 'data.json') TO 'data.parquet'`
   - Subsequent queries are 10-100x faster
   - Perfect for iterative data exploration

## Running the Test

```bash
# Install dependencies
pip install duckdb

# Run benchmark
python3 performance_test.py
```

The test generates synthetic e-commerce order data and compares:
- Standard Python JSON parsing (load all, filter in Python)
- DuckDB querying JSON directly
- DuckDB with Parquet (columnar format)

## Test Operations

All tests perform the same operations:
1. Filter: `WHERE status = 'delivered'`
2. Aggregate: `SUM(price * quantity)` by category
3. Calculate totals and averages

This simulates real-world analytics workloads.

## Key Takeaways from HN Thread

> "DuckDB can query files DIRECTLY - no loading step needed"

> "For medium data (< few GB), full scans are often fast enough"

> "Converting to Parquet once enables much faster repeated queries"

> "DuckDB's CSV/JSON parsers are highly optimized and parallelized"

> "Parquet format enables predicate pushdown and columnar reads"

## When to Use DuckDB

Based on the discussion, DuckDB excels at:

- ✅ Exploratory data analysis on medium datasets
- ✅ ETL pipelines (CSV/JSON → Parquet)
- ✅ Ad-hoc querying of files without a database
- ✅ Data validation and cleaning
- ✅ Joining data from multiple sources/formats
- ✅ Local analytics (replaces SQLite for analytics)
- ✅ Embedding in applications (small binary size)

## Files

- `performance_test.py` - Main benchmark script
- `test_data/` - Generated test datasets (JSONL and Parquet)
- `README.md` - This file

## Requirements

- Python 3.8+
- duckdb Python package

```bash
pip install duckdb
```

## Related Links

- [DuckDB Official Site](https://duckdb.org/)
- [HN Discussion](https://news.ycombinator.com/item?id=46645176)
- [DuckDB JSON Extension](https://duckdb.org/docs/extensions/json.html)
- [Why DuckDB is fast](https://duckdb.org/why_duckdb.html)
