#!/usr/bin/env python3
"""
DuckDB vs JSON/CSV Performance Test
Based on HN discussion: https://news.ycombinator.com/item?id=46645176

Tests the performance advice from the article:
- DuckDB's fast CSV/JSON readers ("The .csv parser is amazing")
- Ability to query files directly without loading into memory
- Performance on medium-sized datasets (100K-1M rows)
- Comparison with standard Python JSON/CSV parsing
"""

import json
import time
import duckdb
import os
import random
import csv
from datetime import datetime, timedelta
from pathlib import Path

# Test configuration
TEST_SIZES = [10000, 100000, 500000]  # Rows to test
DATA_DIR = Path(__file__).parent / "test_data"
DATA_DIR.mkdir(exist_ok=True)


def generate_test_data(num_rows, jsonl_path, csv_path):
    """Generate realistic test data as JSONL and CSV"""
    print(f"Generating {num_rows:,} rows of test data...")
    
    categories = ["electronics", "clothing", "books", "home", "sports"]
    statuses = ["pending", "shipped", "delivered", "cancelled"]
    
    base_date = datetime(2023, 1, 1)
    records = []
    
    for i in range(num_rows):
        record = {
            "id": i + 1,
            "user_id": random.randint(1, 10000),
            "product_id": random.randint(1, 5000),
            "category": random.choice(categories),
            "price": round(random.uniform(5.0, 500.0), 2),
            "quantity": random.randint(1, 10),
            "status": random.choice(statuses),
            "timestamp": (base_date + timedelta(
                days=random.randint(0, 365),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )).isoformat(),
            "rating": random.randint(1, 5) if random.random() > 0.2 else None
        }
        records.append(record)
    
    # Write JSONL
    with open(jsonl_path, 'w') as f:
        for record in records:
            f.write(json.dumps(record) + '\n')
    
    # Write CSV
    with open(csv_path, 'w', newline='') as f:
        if records:
            writer = csv.DictWriter(f, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
    
    jsonl_size = jsonl_path.stat().st_size / (1024 * 1024)
    csv_size = csv_path.stat().st_size / (1024 * 1024)
    print(f"  → Created {jsonl_path.name} ({jsonl_size:.1f} MB)")
    print(f"  → Created {csv_path.name} ({csv_size:.1f} MB)")
    
    return jsonl_path, csv_path


def test_json_parsing(jsonl_path):
    """Test standard Python JSON parsing performance"""
    print("\n  [JSON Parsing] Loading and filtering with Python...")
    
    start = time.time()
    
    # Simulate common operations: load, filter, aggregate
    total_revenue = 0
    delivered_count = 0
    category_totals = {}
    
    with open(jsonl_path, 'r') as f:
        for line in f:
            record = json.loads(line)
            
            # Filter: delivered items only
            if record['status'] == 'delivered':
                delivered_count += 1
                revenue = record['price'] * record['quantity']
                total_revenue += revenue
                
                # Aggregate by category
                cat = record['category']
                category_totals[cat] = category_totals.get(cat, 0) + revenue
    
    elapsed = time.time() - start
    
    print(f"    ✓ Processed in {elapsed:.3f}s")
    print(f"    ✓ Delivered orders: {delivered_count:,}")
    print(f"    ✓ Total revenue: ${total_revenue:,.2f}")
    
    return elapsed


def test_csv_parsing(csv_path):
    """Test standard Python CSV parsing performance"""
    print("\n  [CSV Parsing] Loading and filtering with Python csv module...")
    
    start = time.time()
    
    total_revenue = 0
    delivered_count = 0
    category_totals = {}
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for record in reader:
            # Filter: delivered items only
            if record['status'] == 'delivered':
                delivered_count += 1
                revenue = float(record['price']) * int(record['quantity'])
                total_revenue += revenue
                
                # Aggregate by category
                cat = record['category']
                category_totals[cat] = category_totals.get(cat, 0) + revenue
    
    elapsed = time.time() - start
    
    print(f"    ✓ Processed in {elapsed:.3f}s")
    print(f"    ✓ Delivered orders: {delivered_count:,}")
    print(f"    ✓ Total revenue: ${total_revenue:,.2f}")
    
    return elapsed


def test_duckdb_json(jsonl_path):
    """Test DuckDB querying JSON directly"""
    print("\n  [DuckDB JSON] Querying JSON file directly...")
    
    start = time.time()
    
    conn = duckdb.connect(':memory:')
    
    # DuckDB can query JSON directly - no loading needed!
    # This demonstrates the "just query files" approach from the article
    result = conn.execute(f"""
        SELECT 
            status,
            COUNT(*) as order_count,
            SUM(price * quantity) as total_revenue,
            AVG(price) as avg_price
        FROM read_json_auto('{jsonl_path}')
        WHERE status = 'delivered'
        GROUP BY status
    """).fetchall()
    
    # Also test category aggregation
    categories = conn.execute(f"""
        SELECT 
            category,
            SUM(price * quantity) as revenue
        FROM read_json_auto('{jsonl_path}')
        WHERE status = 'delivered'
        GROUP BY category
        ORDER BY revenue DESC
    """).fetchall()
    
    elapsed = time.time() - start
    conn.close()
    
    print(f"    ✓ Queried in {elapsed:.3f}s")
    if result:
        print(f"    ✓ Delivered orders: {result[0][1]:,}")
        print(f"    ✓ Total revenue: ${result[0][2]:,.2f}")
    
    return elapsed


def test_duckdb_csv(csv_path):
    """Test DuckDB querying CSV directly - showcasing auto type detection"""
    print("\n  [DuckDB CSV] Querying CSV file directly (auto types)...")
    
    start = time.time()
    
    conn = duckdb.connect(':memory:')
    
    # DuckDB's CSV reader is "amazing" per HN discussion
    # Auto assigns types, handles various formats, parallelized
    result = conn.execute(f"""
        SELECT 
            status,
            COUNT(*) as order_count,
            SUM(price * quantity) as total_revenue,
            AVG(price) as avg_price
        FROM read_csv_auto('{csv_path}')
        WHERE status = 'delivered'
        GROUP BY status
    """).fetchall()
    
    elapsed = time.time() - start
    conn.close()
    
    print(f"    ✓ Queried in {elapsed:.3f}s")
    if result:
        print(f"    ✓ Delivered orders: {result[0][1]:,}")
        print(f"    ✓ Total revenue: ${result[0][2]:,.2f}")
        print(f"    ✓ Auto-detected types and parsed CSV")
    
    return elapsed


def test_duckdb_with_indexing(jsonl_path, parquet_path):
    """Test DuckDB with Parquet (columnar format with metadata)"""
    print("\n  [DuckDB Parquet] Converting to Parquet and querying...")
    
    start = time.time()
    
    conn = duckdb.connect(':memory:')
    
    # Convert JSON to Parquet (one-time cost, demonstrates the workflow)
    # Parquet is columnar and has metadata - enables predicate pushdown
    conn.execute(f"""
        COPY (SELECT * FROM read_json_auto('{jsonl_path}'))
        TO '{parquet_path}' (FORMAT PARQUET)
    """)
    
    convert_time = time.time() - start
    
    # Now query the Parquet file
    query_start = time.time()
    result = conn.execute(f"""
        SELECT 
            category,
            COUNT(*) as count,
            SUM(price * quantity) as revenue
        FROM '{parquet_path}'
        WHERE status = 'delivered' AND price > 100
        GROUP BY category
    """).fetchall()
    
    query_time = time.time() - query_start
    total_time = time.time() - start
    conn.close()
    
    print(f"    ✓ Convert to Parquet: {convert_time:.3f}s")
    print(f"    ✓ Query Parquet: {query_time:.3f}s")
    print(f"    ✓ Total time: {total_time:.3f}s")
    
    return total_time, query_time


def run_benchmark():
    """Run complete benchmark suite"""
    print("=" * 70)
    print("DuckDB vs JSON/CSV Parsing Performance Test")
    print("Based on HN Discussion: Why DuckDB is great for data processing")
    print("=" * 70)
    
    results = []
    
    for size in TEST_SIZES:
        print(f"\n{'=' * 70}")
        print(f"TESTING WITH {size:,} ROWS")
        print('=' * 70)
        
        # Generate test data
        jsonl_path = DATA_DIR / f"test_{size}.jsonl"
        csv_path = DATA_DIR / f"test_{size}.csv"
        parquet_path = DATA_DIR / f"test_{size}.parquet"
        
        if not jsonl_path.exists() or not csv_path.exists():
            generate_test_data(size, jsonl_path, csv_path)
        else:
            print(f"Using existing test files")
        
        # Run tests
        json_time = test_json_parsing(jsonl_path)
        csv_time = test_csv_parsing(csv_path)
        duckdb_json_time = test_duckdb_json(jsonl_path)
        duckdb_csv_time = test_duckdb_csv(csv_path)
        duckdb_parquet_time, parquet_query_only = test_duckdb_with_indexing(
            jsonl_path, parquet_path
        )
        
        # Calculate speedups
        speedup_vs_json = json_time / duckdb_json_time if duckdb_json_time > 0 else 0
        speedup_vs_csv = csv_time / duckdb_csv_time if duckdb_csv_time > 0 else 0
        speedup_parquet = json_time / parquet_query_only if parquet_query_only > 0 else 0
        
        results.append({
            'rows': size,
            'json_time': json_time,
            'csv_time': csv_time,
            'duckdb_json': duckdb_json_time,
            'duckdb_csv': duckdb_csv_time,
            'duckdb_parquet': duckdb_parquet_time,
            'parquet_query': parquet_query_only,
            'speedup_json': speedup_vs_json,
            'speedup_csv': speedup_vs_csv,
            'speedup_parquet': speedup_parquet
        })
        
        print(f"\n  📊 Speedup vs Python:")
        print(f"     DuckDB (JSON): {speedup_vs_json:.1f}x faster than Python JSON")
        print(f"     DuckDB (CSV): {speedup_vs_csv:.1f}x faster than Python CSV")
        print(f"     DuckDB (Parquet): {speedup_parquet:.1f}x faster than Python JSON")
    
    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY RESULTS")
    print('=' * 70)
    print(f"{'Rows':>10} | {'Py JSON':>8} | {'Py CSV':>8} | {'DDB JSON':>8} | {'DDB CSV':>8} | {'Parquet':>8}")
    print("-" * 70)
    
    for r in results:
        print(f"{r['rows']:>10,} | {r['json_time']:>7.3f}s | {r['csv_time']:>7.3f}s | "
              f"{r['duckdb_json']:>7.3f}s | {r['duckdb_csv']:>7.3f}s | {r['parquet_query']:>7.3f}s")
    
    print("\n💡 Key Takeaways from HN Discussion:")
    print("  • DuckDB can query files DIRECTLY - no loading step needed")
    print("  • DuckDB's CSV parser is 'amazing' - auto assigns types, parallelized")
    print("  • Parquet format enables predicate pushdown and columnar reads")
    print("  • For medium data (< few GB), full scans are often fast enough")
    print("  • DuckDB's CSV/JSON parsers are highly optimized")
    print("  • Converting to Parquet once enables much faster repeated queries")
    
    return results


if __name__ == "__main__":
    try:
        results = run_benchmark()
        
        print(f"\n✅ Benchmark complete! Test data saved in: {DATA_DIR}")
        print(f"📁 Files created:")
        for f in sorted(DATA_DIR.glob("test_*")):
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"   - {f.name} ({size_mb:.1f} MB)")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
