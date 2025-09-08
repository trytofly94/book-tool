"""
Performance benchmarking framework for ASIN lookup optimizations.

This module provides comprehensive benchmarking tools to measure and compare
ASIN lookup performance before and after optimizations.
"""

import time
import json
import statistics
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

from .book import Book
from .asin_lookup import ASINLookupService


@dataclass
class BenchmarkResult:
    """Individual benchmark test result."""

    test_name: str
    book_count: int
    total_time: float
    average_time_per_book: float
    success_count: int
    success_rate: float
    cache_hits: int
    cache_hit_rate: float
    error_count: int
    errors: List[str]
    timestamp: str

    # Performance metrics
    requests_per_second: float
    cache_efficiency: float  # (cache_hits + success_count) / book_count

    # Detailed breakdown
    source_breakdown: Dict[str, int]  # Count by source
    confidence_distribution: Dict[str, int]  # Low/Medium/High confidence
    timing_percentiles: Dict[str, float]  # P50, P90, P95, P99

    # Memory and resource usage
    peak_memory_usage: Optional[int] = None
    network_requests_made: Optional[int] = None
    rate_limit_delays: Optional[float] = None


@dataclass
class BenchmarkComparison:
    """Comparison between two benchmark results."""

    baseline: BenchmarkResult
    optimized: BenchmarkResult
    improvements: Dict[str, float]  # Percentage improvements
    regressions: Dict[str, float]  # Percentage regressions
    overall_improvement: float  # Overall performance improvement percentage


class ASINLookupBenchmark:
    """
    Comprehensive benchmarking framework for ASIN lookup performance.

    Provides standardized testing methodology and comparison capabilities.
    """

    def __init__(self, asin_service: ASINLookupService):
        """
        Initialize benchmark framework.

        Args:
            asin_service: ASIN lookup service to benchmark
        """
        self.asin_service = asin_service
        self.logger = logging.getLogger(__name__)

        # Benchmark configuration
        self.warmup_runs = 3
        self.measurement_runs = 5

    def run_benchmark(
        self,
        books: List[Book],
        test_name: str = "ASIN Lookup Benchmark",
        parallel_workers: Optional[int] = None,
        sources: Optional[List[str]] = None,
        include_warmup: bool = True,
        detailed_timing: bool = True,
    ) -> BenchmarkResult:
        """
        Run comprehensive benchmark on book collection.

        Args:
            books: Books to test ASIN lookup on
            test_name: Name for this benchmark run
            parallel_workers: Number of parallel workers to use
            sources: Sources to test (defaults to all configured)
            include_warmup: Whether to run warmup iterations
            detailed_timing: Whether to collect detailed timing data

        Returns:
            Comprehensive benchmark result
        """
        self.logger.info(f"Starting benchmark: {test_name} with {len(books)} books")

        # Clear cache to ensure clean test
        if hasattr(self.asin_service.cache_manager, "clear"):
            self.asin_service.cache_manager.clear()

        # Warmup runs
        if include_warmup:
            self.logger.info(f"Running {self.warmup_runs} warmup iterations...")
            for i in range(self.warmup_runs):
                self._run_single_benchmark_iteration(
                    books[: min(5, len(books))], parallel_workers, sources
                )

        # Actual benchmark runs
        self.logger.info(f"Running {self.measurement_runs} measurement iterations...")
        run_results = []

        for run_idx in range(self.measurement_runs):
            self.logger.info(f"Measurement run {run_idx + 1}/{self.measurement_runs}")

            run_start = time.time()
            results = self._run_single_benchmark_iteration(
                books, parallel_workers, sources
            )
            run_time = time.time() - run_start

            run_results.append(
                {"results": results, "total_time": run_time, "run_index": run_idx}
            )

        # Aggregate results
        return self._aggregate_benchmark_results(
            run_results, test_name, books, detailed_timing
        )

    def _run_single_benchmark_iteration(
        self,
        books: List[Book],
        parallel_workers: Optional[int],
        sources: Optional[List[str]],
    ) -> List:
        """Run a single benchmark iteration."""
        progress_data = {"completed": 0, "total": len(books)}

        def progress_callback(description: str):
            progress_data["completed"] += 1

        # Record stats before
        stats_before = self.asin_service.get_performance_stats()

        # Run the actual lookup
        start_time = time.time()
        results = self.asin_service.batch_update(
            books=books,
            sources=sources,
            parallel=parallel_workers,
            progress_callback=progress_callback,
        )
        end_time = time.time()

        # Record stats after
        stats_after = self.asin_service.get_performance_stats()

        return {
            "results": results,
            "start_time": start_time,
            "end_time": end_time,
            "total_time": end_time - start_time,
            "stats_before": stats_before,
            "stats_after": stats_after,
        }

    def _aggregate_benchmark_results(
        self,
        run_results: List[Dict],
        test_name: str,
        books: List[Book],
        detailed_timing: bool,
    ) -> BenchmarkResult:
        """Aggregate multiple benchmark run results."""

        # Extract timing data from all runs
        total_times = [run["total_time"] for run in run_results]

        # Use the median run for detailed analysis
        median_run_idx = len(total_times) // 2
        sorted_runs = sorted(run_results, key=lambda x: x["total_time"])
        median_run = sorted_runs[median_run_idx]["results"]

        results = median_run["results"]

        # Calculate basic metrics
        book_count = len(books)
        success_count = sum(1 for r in results if r.success)
        success_rate = success_count / book_count * 100 if book_count > 0 else 0.0
        cache_hits = sum(1 for r in results if r.from_cache)
        cache_hit_rate = cache_hits / book_count * 100 if book_count > 0 else 0.0

        # Average timing across all runs
        avg_total_time = statistics.mean(total_times)
        avg_time_per_book = avg_total_time / book_count if book_count > 0 else 0.0
        requests_per_second = book_count / avg_total_time if avg_total_time > 0 else 0.0

        # Cache efficiency
        cache_efficiency = (
            (cache_hits + success_count) / book_count * 100 if book_count > 0 else 0.0
        )

        # Source breakdown
        source_breakdown = {}
        for result in results:
            if result.success and result.source:
                source_breakdown[result.source] = (
                    source_breakdown.get(result.source, 0) + 1
                )

        # Confidence distribution
        confidence_distribution = {"low": 0, "medium": 0, "high": 0}
        for result in results:
            if result.success and result.metadata and "confidence" in result.metadata:
                confidence = result.metadata["confidence"]
                if confidence < 0.5:
                    confidence_distribution["low"] += 1
                elif confidence < 0.8:
                    confidence_distribution["medium"] += 1
                else:
                    confidence_distribution["high"] += 1

        # Timing percentiles (if detailed timing enabled)
        timing_percentiles = {}
        if detailed_timing:
            individual_times = [r.lookup_time for r in results if r.lookup_time > 0]
            if individual_times:
                timing_percentiles = {
                    "p50": statistics.median(individual_times),
                    "p90": statistics.quantiles(individual_times, n=10)[8],
                    "p95": statistics.quantiles(individual_times, n=20)[18],
                    "p99": statistics.quantiles(individual_times, n=100)[98],
                }

        # Error analysis
        error_count = sum(1 for r in results if not r.success)
        errors = [r.error for r in results if not r.success and r.error][
            :10
        ]  # First 10 errors

        # Performance stats from ASIN service
        perf_stats = self.asin_service.get_performance_stats()
        rate_limit_stats = perf_stats.get("rate_limiting", {})

        # Calculate total network requests and delays
        network_requests_made = 0
        rate_limit_delays = 0.0

        for domain_stats in rate_limit_stats.values():
            if isinstance(domain_stats, dict):
                network_requests_made += domain_stats.get("requests_made", 0)
                rate_limit_delays += domain_stats.get("total_delay_time", 0.0)

        return BenchmarkResult(
            test_name=test_name,
            book_count=book_count,
            total_time=avg_total_time,
            average_time_per_book=avg_time_per_book,
            success_count=success_count,
            success_rate=success_rate,
            cache_hits=cache_hits,
            cache_hit_rate=cache_hit_rate,
            error_count=error_count,
            errors=errors,
            timestamp=datetime.now().isoformat(),
            requests_per_second=requests_per_second,
            cache_efficiency=cache_efficiency,
            source_breakdown=source_breakdown,
            confidence_distribution=confidence_distribution,
            timing_percentiles=timing_percentiles,
            network_requests_made=network_requests_made,
            rate_limit_delays=rate_limit_delays,
        )

    def compare_benchmarks(
        self, baseline: BenchmarkResult, optimized: BenchmarkResult
    ) -> BenchmarkComparison:
        """
        Compare two benchmark results and calculate improvements.

        Args:
            baseline: Baseline benchmark result
            optimized: Optimized benchmark result

        Returns:
            Detailed comparison with improvements and regressions
        """
        improvements = {}
        regressions = {}

        # Define metrics to compare (lower is better)
        lower_is_better = [
            "total_time",
            "average_time_per_book",
            "error_count",
            "rate_limit_delays",
        ]

        # Define metrics to compare (higher is better)
        higher_is_better = [
            "success_rate",
            "cache_hit_rate",
            "requests_per_second",
            "cache_efficiency",
        ]

        def calculate_improvement(
            baseline_val: float, optimized_val: float, higher_better: bool
        ) -> float:
            """Calculate improvement percentage."""
            if baseline_val == 0:
                return 0.0

            if higher_better:
                return ((optimized_val - baseline_val) / baseline_val) * 100
            else:
                return ((baseline_val - optimized_val) / baseline_val) * 100

        # Compare all metrics
        for metric in lower_is_better:
            baseline_val = getattr(baseline, metric, 0)
            optimized_val = getattr(optimized, metric, 0)
            improvement = calculate_improvement(baseline_val, optimized_val, False)

            if improvement > 0:
                improvements[metric] = improvement
            elif improvement < 0:
                regressions[metric] = abs(improvement)

        for metric in higher_is_better:
            baseline_val = getattr(baseline, metric, 0)
            optimized_val = getattr(optimized, metric, 0)
            improvement = calculate_improvement(baseline_val, optimized_val, True)

            if improvement > 0:
                improvements[metric] = improvement
            elif improvement < 0:
                regressions[metric] = abs(improvement)

        # Calculate overall improvement (weighted average)
        # Weight total_time most heavily as it's the primary metric
        weights = {
            "total_time": 0.4,
            "success_rate": 0.2,
            "cache_hit_rate": 0.2,
            "requests_per_second": 0.2,
        }

        weighted_improvement = 0.0
        for metric, weight in weights.items():
            improvement = improvements.get(metric, 0) - regressions.get(metric, 0)
            weighted_improvement += improvement * weight

        return BenchmarkComparison(
            baseline=baseline,
            optimized=optimized,
            improvements=improvements,
            regressions=regressions,
            overall_improvement=weighted_improvement,
        )

    def save_benchmark_result(self, result: BenchmarkResult, file_path: Path):
        """Save benchmark result to JSON file."""
        try:
            with open(file_path, "w") as f:
                json.dump(asdict(result), f, indent=2, default=str)
            self.logger.info(f"Saved benchmark result to {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save benchmark result: {e}")

    def load_benchmark_result(self, file_path: Path) -> Optional[BenchmarkResult]:
        """Load benchmark result from JSON file."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return BenchmarkResult(**data)
        except Exception as e:
            self.logger.error(f"Failed to load benchmark result: {e}")
            return None

    def print_benchmark_summary(self, result: BenchmarkResult):
        """Print human-readable benchmark summary."""
        print(f"\n{'='*60}")
        print(f"BENCHMARK RESULTS: {result.test_name}")
        print(f"{'='*60}")
        print(f"Test Date: {result.timestamp}")
        print(f"Books Tested: {result.book_count}")
        print()

        print("PERFORMANCE METRICS:")
        print(f"  Total Time: {result.total_time:.2f}s")
        print(f"  Avg Time/Book: {result.average_time_per_book:.3f}s")
        print(f"  Requests/Second: {result.requests_per_second:.2f}")
        print()

        print("SUCCESS METRICS:")
        print(
            f"  Success Rate: {result.success_rate:.1f}% ({result.success_count}/{result.book_count})"
        )
        print(
            f"  Cache Hit Rate: {result.cache_hit_rate:.1f}% ({result.cache_hits}/{result.book_count})"
        )
        print(f"  Cache Efficiency: {result.cache_efficiency:.1f}%")
        print(f"  Error Count: {result.error_count}")
        print()

        if result.source_breakdown:
            print("SOURCE BREAKDOWN:")
            for source, count in sorted(result.source_breakdown.items()):
                print(f"  {source}: {count} books")
            print()

        if result.confidence_distribution and any(
            result.confidence_distribution.values()
        ):
            print("CONFIDENCE DISTRIBUTION:")
            total_confident = sum(result.confidence_distribution.values())
            for level, count in result.confidence_distribution.items():
                percentage = count / total_confident * 100 if total_confident > 0 else 0
                print(f"  {level.title()}: {count} ({percentage:.1f}%)")
            print()

        if result.timing_percentiles:
            print("TIMING PERCENTILES:")
            for percentile, time_val in result.timing_percentiles.items():
                print(f"  {percentile.upper()}: {time_val:.3f}s")
            print()

        if result.network_requests_made:
            print("NETWORK EFFICIENCY:")
            print(f"  Network Requests: {result.network_requests_made}")
            print(f"  Rate Limit Delays: {result.rate_limit_delays:.2f}s")
            efficiency = (
                (result.success_count / result.network_requests_made * 100)
                if result.network_requests_made > 0
                else 0
            )
            print(f"  Request Efficiency: {efficiency:.1f}%")

        print(f"{'='*60}\n")

    def print_benchmark_comparison(self, comparison: BenchmarkComparison):
        """Print human-readable benchmark comparison."""
        print(f"\n{'='*60}")
        print("BENCHMARK COMPARISON")
        print(f"{'='*60}")
        print(f"Baseline: {comparison.baseline.test_name}")
        print(f"Optimized: {comparison.optimized.test_name}")
        print()

        print(f"OVERALL IMPROVEMENT: {comparison.overall_improvement:+.1f}%")
        print()

        if comparison.improvements:
            print("IMPROVEMENTS:")
            for metric, improvement in sorted(
                comparison.improvements.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {metric.replace('_', ' ').title()}: +{improvement:.1f}%")
            print()

        if comparison.regressions:
            print("REGRESSIONS:")
            for metric, regression in sorted(
                comparison.regressions.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {metric.replace('_', ' ').title()}: -{regression:.1f}%")
            print()

        # Key metrics comparison table
        print("KEY METRICS COMPARISON:")
        print(f"{'Metric':<20} {'Baseline':<12} {'Optimized':<12} {'Change':<10}")
        print("-" * 60)

        key_metrics = [
            ("total_time", "Total Time", "s"),
            ("success_rate", "Success Rate", "%"),
            ("cache_hit_rate", "Cache Hit Rate", "%"),
            ("requests_per_second", "Requests/Sec", ""),
        ]

        for attr, name, unit in key_metrics:
            baseline_val = getattr(comparison.baseline, attr)
            optimized_val = getattr(comparison.optimized, attr)

            if baseline_val != 0:
                change_pct = ((optimized_val - baseline_val) / baseline_val) * 100
                change_str = f"{change_pct:+.1f}%"
            else:
                change_str = "N/A"

            print(
                f"{name:<20} {baseline_val:<12.2f} {optimized_val:<12.2f} {change_str:<10}"
            )

        print(f"{'='*60}\n")
