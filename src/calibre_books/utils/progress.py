"""
Progress management utilities for Calibre Books CLI.

This module provides progress tracking capabilities for long-running operations
using Rich progress bars and console output.
"""

import time
from contextlib import contextmanager
from typing import Optional, Callable

from rich.console import Console
from rich.progress import (
    Progress,
    TaskID,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
)

console = Console()


class ProgressManager:
    """
    Context manager for tracking progress of operations.

    Provides both spinner-based progress (for indeterminate operations)
    and bar-based progress (for operations with known total).

    Usage:
        # Spinner progress for unknown duration
        with ProgressManager("Processing files") as progress:
            # Do work
            progress.update("Found 10 files")
            # More work
            progress.update("Processing file 1")

        # Bar progress for known total
        with ProgressManager("Converting files", total=100) as progress:
            for i in range(100):
                # Do work
                progress.update(i + 1)
    """

    def __init__(
        self,
        description: str,
        total: Optional[int] = None,
        show_speed: bool = False,
    ):
        """
        Initialize progress manager.

        Args:
            description: Description of the operation
            total: Total number of items to process (None for spinner)
            show_speed: Whether to show processing speed
        """
        self.description = description
        self.total = total
        self.show_speed = show_speed
        self.progress: Optional[Progress] = None
        self.task_id: Optional[TaskID] = None
        self.start_time: Optional[float] = None

    def __enter__(self) -> "ProgressManager":
        """Enter context manager and start progress display."""
        self.start_time = time.time()

        # Configure progress columns based on operation type
        if self.total is not None:
            # Bar progress for determinate operations
            columns = [
                TextColumn("{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
            ]

            if self.total > 10:  # Only show time remaining for longer operations
                columns.append(TimeRemainingColumn())
        else:
            # Spinner progress for indeterminate operations
            columns = [
                SpinnerColumn(),
                TextColumn("{task.description}"),
                TimeElapsedColumn(),
            ]

        self.progress = Progress(*columns, console=console)
        self.progress.start()

        # Add the task
        self.task_id = self.progress.add_task(
            description=self.description,
            total=self.total,
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and stop progress display."""
        if self.progress:
            self.progress.stop()

        # Show completion message
        if exc_type is None and self.start_time:
            elapsed = time.time() - self.start_time
            console.print(
                f"[green]✓[/green] {self.description} completed in {elapsed:.1f}s"
            )
        elif exc_type is not None:
            console.print(f"[red]✗[/red] {self.description} failed")

    def update(
        self,
        advance: Optional[int] = None,
        completed: Optional[int] = None,
        description: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Update progress display.

        Args:
            advance: Number of items to advance by
            completed: Total number of completed items
            description: Updated task description
            **kwargs: Additional fields to update
        """
        if not self.progress or self.task_id is None:
            return

        update_kwargs = {}

        if advance is not None:
            update_kwargs["advance"] = advance
        elif completed is not None:
            update_kwargs["completed"] = completed

        if description is not None:
            update_kwargs["description"] = description

        # Add any additional kwargs
        update_kwargs.update(kwargs)

        self.progress.update(self.task_id, **update_kwargs)

    def set_total(self, total: int) -> None:
        """Set or update the total number of items."""
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, total=total)
            self.total = total


@contextmanager
def simple_progress(message: str):
    """
    Simple progress context manager that just shows start/end messages.

    Usage:
        with simple_progress("Downloading file"):
            # Do work
            pass
    """
    console.print(f"[blue]→[/blue] {message}...")
    start_time = time.time()

    try:
        yield
        elapsed = time.time() - start_time
        console.print(f"[green]✓[/green] {message} completed in {elapsed:.1f}s")
    except Exception:
        console.print(f"[red]✗[/red] {message} failed")
        raise


def create_progress_callback(
    progress_manager: ProgressManager,
) -> Callable[[int], None]:
    """
    Create a callback function for use with external libraries.

    Args:
        progress_manager: ProgressManager instance to update

    Returns:
        Callback function that accepts progress updates
    """

    def callback(current: int, total: Optional[int] = None) -> None:
        if total is not None and progress_manager.total is None:
            progress_manager.set_total(total)

        progress_manager.update(completed=current)

    return callback


class BatchProgressManager:
    """
    Progress manager for batch operations with multiple sub-tasks.

    Usage:
        with BatchProgressManager("Processing books", total=10) as batch:
            for book in books:
                with batch.task(f"Processing {book.title}") as task:
                    # Do work
                    task.update("Converting format")
                    # More work
                    task.update("Updating metadata")
    """

    def __init__(self, description: str, total: int):
        self.description = description
        self.total = total
        self.progress: Optional[Progress] = None
        self.main_task_id: Optional[TaskID] = None
        self.completed_items = 0

    def __enter__(self) -> "BatchProgressManager":
        """Enter context manager."""
        columns = [
            TextColumn("{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ]

        self.progress = Progress(*columns, console=console)
        self.progress.start()

        self.main_task_id = self.progress.add_task(
            description=self.description,
            total=self.total,
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if self.progress:
            self.progress.stop()

    @contextmanager
    def task(self, description: str):
        """
        Context manager for individual tasks within the batch.

        Args:
            description: Description of the current task
        """
        # Create subtask progress
        task_progress = ProgressManager(description)

        try:
            with task_progress:
                yield task_progress

            # Update main progress
            self.completed_items += 1
            if self.progress and self.main_task_id is not None:
                self.progress.update(
                    self.main_task_id,
                    completed=self.completed_items,
                )

        except Exception:
            # Still update progress even if task failed
            self.completed_items += 1
            if self.progress and self.main_task_id is not None:
                self.progress.update(
                    self.main_task_id,
                    completed=self.completed_items,
                )
            raise
