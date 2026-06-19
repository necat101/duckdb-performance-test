#!/usr/bin/env python3
"""
DuckDB vs JSON Performance Test
Based on HN discussion: https://news.ycombinator.com/item?id=46645176

Tests the performance advice from the article:
- DuckDB's fast CSV/JSON readers
- Ability to query files directly without loading into memory
- Performance on medium-sized datasets (100K-1M rows)
- Comparison with standard Python JSON parsing
"""

import json
import time
import duckdb
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

# Test configuration
TEST_SIZES = [10000, 100000, 500000]  # Rows to test
DATA_DIR = Path(__file__).parent / "test_data"
DATA_DIR.mkdir(exist_ok=True)


def generate_test_data(num_rows, output_path):
    """Generate realistic test data as JSONL"""
    print(f"Generating {num_rows:,} rows of test data...")
    
    categories = ["electronics", "clothing", "books", "home", "sports"]
    statuses = ["pending", "shipped", "delivered", "cancelled"]
    
    with open(output_path, 'w') as f:
        base_date = datetime(2023, 1, 1)
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
            f.write(json.dumps(record) + '\n')
    
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  → Created {output_path.name} ({size_mb:.1f} MB)")
    return output_path


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
    print("DuckDB vs JSON Parsing Performance Test")
    print("Based on HN Discussion: Why DuckDB is great for data processing")
    print("=" * 70)
    
    results = []
    
    for size in TEST_SIZES:
        print(f"\n{'=' * 70}")
        print(f"TESTING WITH {size:,} ROWS")
        print('=' * 70)
        
        # Generate test data
        jsonl_path = DATA_DIR / f"test_{size}.jsonl"
        parquet_path = DATA_DIR / f"test_{size}.parquet"
        
        if not jsonl_path.exists():
            generate_test_data(size, jsonl_path)
        else:
            print(f"Using existing {jsonl_path.name}")
        
        # Run tests
        json_time = test_json_parsing(jsonl_path)
        duckdb_json_time = test_duckdb_json(jsonl_path)
        duckdb_parquet_time, parquet_query_only = test_duckdb_with_indexing(
            jsonl_path, parquet_path
        )
        
        # Calculate speedups
        speedup_vs_json = json_time / duckdb_json_time if duckdb_json_time > 0 else 0
        speedup_parquet = json_time / parquet_query_only if parquet_query_only > 0 else 0
        
        results.append({
            'rows': size,
            'json_time': json_time,
            'duckdb_json': duckdb_json_time,
            'duckdb_parquet': duckdb_parquet_time,
            'parquet_query': parquet_query_only,
            'speedup_json': speedup_vs_json,
            'speedup_parquet': speedup_parquet
        })
        
        print(f"\n  📊 Speedup vs Python JSON:")
        print(f"     DuckDB (JSON): {speedup_vs_json:.1f}x faster")
        print(f"     DuckDB (Parquet): {speedup_parquet:.1f}x faster")
    
    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY RESULTS")
    print('=' * 70)
    print(f"{'Rows':>10} | {'Python':>8} | {'DuckDB':>8} | {'Parquet':>8} | {'Speedup':>8}")
    print("-" * 70)
    
    for r in results:
        print(f"{r['rows']:>10,} | {r['json_time']:>7.3f}s | "
              f"{r['duckdb_json']:>7.3f}s | {r['parquet_query']:>7.3f}s | "
              f"{r['speedup_parquet']:>7.1f}x")
    
    print("\n💡 Key Takeaways from HN Discussion:")
    print("  • DuckDB can query files DIRECTLY - no loading step needed")
    print("  • Parquet format enables predicate pushdown and columnar reads")
    print("  • For medium data (< few GB), full scans are often fast enough")
    print("  • DuckDB's CSV/JSON parsers are highly optimized and parallelized")
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
