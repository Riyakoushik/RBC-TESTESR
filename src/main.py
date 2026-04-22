"""
Main CLI entry point for RBC-TESTER Document Conversion Pipeline.
Provides live progress monitoring with Rich terminal UI.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional, List

import typer
from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table
from rich.text import Text
from loguru import logger

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config, reload_config, get_project_root
from src.utils import get_input_files, ConversionState, ensure_dir, detect_file_type, is_scanned_pdf
from src.monitor import SystemMonitor, ProgressTracker
from src.converter import BatchProcessor, DocumentConverterPipeline

# Initialize console
console = Console()

# Typer app
app = typer.Typer(
    name="rbc-tester",
    help="RBC-TESTER: Local-first document conversion pipeline",
    rich_markup_mode="rich"
)


def setup_logging(log_dir: Path, level: str = "INFO"):
    """Configure loguru logging with file and console output."""
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Remove default handler
    logger.remove()
    
    # Console handler with Rich
    logger.add(
        lambda msg: console.print(msg, end=""),
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        colorize=True
    )
    
    # File handler
    log_file = log_dir / "conversion.log"
    logger.add(
        str(log_file),
        rotation="10 MB",
        retention=3,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    )


def create_progress_display():
    """Create Rich progress bar with custom columns."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(complete_style="green", finished_style="green"),
        TaskProgressColumn(),
        TextColumn("[{task.completed}/{task.total}]"),
        TimeRemainingColumn(),
        console=console,
        expand=True
    )


def create_metrics_table(monitor: SystemMonitor, tracker: ProgressTracker) -> Table:
    """Create system metrics table for display."""
    metrics = monitor.get_formatted_metrics()
    stats = tracker.get_stats()
    
    table = Table(show_header=False, box=box.ROUNDED, border_style="blue")
    table.add_column("Metric", style="cyan", width=12)
    table.add_column("Value", style="white")
    
    table.add_row("CPU", metrics["cpu"])
    table.add_row("Memory", metrics["memory"])
    table.add_row("Disk Free", metrics["disk_free"])
    table.add_row("Files/min", metrics["files_per_min"])
    table.add_row("", "")
    table.add_row("Progress", f"{stats['percent']:.1f}%")
    table.add_row("ETA", stats["eta"])
    table.add_row("Elapsed", stats["elapsed"])
    
    return table


def create_status_table(tracker: ProgressTracker) -> Table:
    """Create file processing status table."""
    stats = tracker.get_stats()
    
    table = Table(show_header=False, box=box.ROUNDED, border_style="green")
    table.add_column("Label", style="cyan")
    table.add_column("Count", justify="right", style="white")
    
    table.add_row("Total Files", str(stats['total']))
    table.add_row("[green]Successful[/green]", str(stats['successful']))
    table.add_row("[red]Failed[/red]", str(stats['failed']))
    table.add_row("[yellow]Remaining[/yellow]", str(stats['total'] - stats['processed']))
    table.add_row("", "")
    table.add_row("Extracted", f"{stats['total_text_mb']:.2f} MB")
    
    return table


def run_conversion_with_ui(files: List[str], config) -> dict:
    """
    Run conversion with live Rich UI.
    
    Args:
        files: List of files to process
        config: Application configuration
    
    Returns:
        Processing results summary
    """
    if not files:
        console.print("[yellow]No files found to process[/yellow]")
        return {"total": 0, "successful": 0, "failed": 0}
    
    # Initialize state and tracking
    state = ConversionState()
    pending = state.get_pending_files(files)
    
    if not pending:
        console.print("[green]All files already processed![/green]")
        return {
            "total": len(files),
            "successful": len(state.completed),
            "failed": len(state.failed),
            "skipped": len(files) - len(state.completed) - len(state.failed)
        }
    
    # Initialize monitor and processor
    monitor = SystemMonitor()
    tracker = ProgressTracker(len(files))
    processor = BatchProcessor()
    
    # Create layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=1)
    )
    
    # Create progress
    progress = create_progress_display()
    task_id = progress.add_task("Converting files...", total=len(pending))
    
    # Results
    results = {
        "total": len(files),
        "successful": 0,
        "failed": 0,
        "total_text_bytes": 0
    }
    
    console.print(f"[bold green]Starting conversion of {len(pending)} files...[/bold green]")
    console.print(f"[dim]Output directory: {config.paths.output_dir}[/dim]\n")
    
    # Live display
    with Live(layout, refresh_per_second=2, console=console) as live:
        batch_size = config.processing.batch_size
        
        for i in range(0, len(pending), batch_size):
            batch = pending[i:i + batch_size]
            
            # Check resources before batch
            if monitor.should_pause():
                layout["footer"].update(
                    Panel("[yellow]Waiting for resources...[/yellow]", border_style="yellow")
                )
                monitor.wait_for_resources(timeout=60)
            
            # Process batch
            for file_path in batch:
                tracker.start_file(file_path)
                
                try:
                    # Update display
                    filename = Path(file_path).name
                    layout["header"].update(
                        Panel(f"[bold]Current:[/bold] [cyan]{filename}[/cyan]", 
                              border_style="blue")
                    )
                    
                    # Convert file
                    output_path, success = processor.converter.convert_file(file_path)
                    
                    # Get output size
                    text_size = 0
                    if success and os.path.exists(output_path):
                        text_size = os.path.getsize(output_path)
                    
                    tracker.complete_file(success, text_size)
                    
                    if success:
                        results["successful"] += 1
                        results["total_text_bytes"] += text_size
                    else:
                        results["failed"] += 1
                    
                    # Update progress
                    progress.update(task_id, advance=1)
                    
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    tracker.complete_file(False)
                    results["failed"] += 1
                    progress.update(task_id, advance=1)
                
                # Update display panels
                layout["left"].update(Panel(progress, border_style="green", title="Progress"))
                layout["right"].update(
                    Panel(create_metrics_table(monitor, tracker), 
                          border_style="blue", title="System")
                )
            
            # Batch delay for thermal management
            if config.processing.batch_delay > 0 and i + batch_size < len(pending):
                time.sleep(config.processing.batch_delay)
    
    return results


@app.command()
def convert(
    input_dir: Optional[str] = typer.Option(None, "--input", "-i", help="Input directory"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume from previous state"),
    skip_existing: bool = typer.Option(True, "--skip-existing/--no-skip", help="Skip already converted files"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Convert all documents in input directory to clean markdown/text files.
    """
    # Load configuration
    if config_file:
        reload_config(config_file)
    
    config = get_config()
    project_root = get_project_root()
    
    # Override with CLI arguments
    if input_dir:
        config.paths.input_dir = input_dir
    if output_dir:
        config.paths.output_dir = output_dir
    if not resume:
        config.processing.auto_resume = False
    if not skip_existing:
        config.processing.skip_existing = False
    
    # Setup logging
    log_level = "DEBUG" if verbose else config.logging.level
    setup_logs_dir = project_root / config.paths.logs_dir
    setup_logging(setup_logs_dir, log_level)
    
    # Ensure directories exist
    input_path = project_root / config.paths.input_dir
    output_path = project_root / config.paths.output_dir
    ensure_dir(str(input_path))
    ensure_dir(str(output_path))
    
    logger.info(f"RBC-TESTER Document Conversion Pipeline")
    logger.info(f"Input: {input_path}")
    logger.info(f"Output: {output_path}")
    
    # Get files to process
    files = get_input_files()
    
    if not files:
        console.print(f"[yellow]No supported files found in {input_path}[/yellow]")
        console.print("[dim]Supported formats: PDF, DOCX, PPTX, EPUB, images, text files[/dim]")
        raise typer.Exit(1)
    
    console.print(f"[green]Found {len(files)} files to process[/green]")
    
    # Clear state if not resuming
    if not config.processing.auto_resume:
        state = ConversionState()
        state.reset()
        console.print("[yellow]State reset - processing all files[/yellow]")
    
    # Run conversion with UI
    results = run_conversion_with_ui(files, config)
    
    # Final summary
    console.print()
    console.print("[bold green]Conversion Complete![/bold green]")
    console.print(f"  Total files: {results['total']}")
    console.print(f"  [green]Successful: {results['successful']}[/green]")
    console.print(f"  [red]Failed: {results.get('failed', 0)}[/red]")
    console.print(f"  Extracted: {results.get('total_text_bytes', 0) / (1024*1024):.2f} MB")
    
    # Write final summary
    from src.utils import write_summary, write_failed_files
    
    write_summary(
        total=results['total'],
        successful=results['successful'],
        failed=results.get('failed', 0),
        total_text=results.get('total_text_bytes', 0)
    )
    
    # Check for failures
    state = ConversionState()
    if state.failed:
        write_failed_files(list(state.failed))
        console.print(f"\n[yellow]Failed files logged to: {config.paths.failed_files_log}[/yellow]")
    
    if results.get('failed', 0) > 0:
        raise typer.Exit(1)


@app.command()
def convert_single(
    file: str = typer.Argument(..., help="Path to file to convert"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """
    Convert a single file.
    """
    if config_file:
        reload_config(config_file)
    
    config = get_config()
    
    if not os.path.exists(file):
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)
    
    console.print(f"[bold]Converting:[/bold] {file}")
    
    pipeline = DocumentConverterPipeline()
    
    # Override output if specified
    if output:
        ensure_dir(os.path.dirname(output))
        from src.utils import get_file_hash
        
        # Manual conversion with custom output
        file_type = detect_file_type(file)
        
        if file_type == "document":
            from src.converter import DocumentConverterPipeline
            conv = DocumentConverterPipeline()
            success = conv._convert_document(file, output)
        elif file_type == "image":
            from src.converter import DocumentConverterPipeline
            conv = DocumentConverterPipeline()
            success = conv._convert_image(file, output)
        elif file_type == "text":
            from src.converter import DocumentConverterPipeline
            conv = DocumentConverterPipeline()
            success = conv._convert_text(file, output)
        else:
            console.print(f"[red]Unsupported file type[/red]")
            raise typer.Exit(1)
    else:
        output_path, success = pipeline.convert_file(file)
        output = output_path
    
    if success:
        console.print(f"[green]Success![/green] Output: {output}")
        # Show file size
        if os.path.exists(output):
            size = os.path.getsize(output)
            console.print(f"[dim]Size: {size / 1024:.1f} KB[/dim]")
    else:
        console.print(f"[red]Conversion failed[/red]")
        raise typer.Exit(1)


@app.command()
def status():
    """
    Show current conversion status and statistics.
    """
    state = ConversionState()
    config = get_config()
    
    files = get_input_files()
    pending = state.get_pending_files(files)
    
    table = Table(title="RBC-TESTER Conversion Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="white")
    
    table.add_row("Total Files", str(len(files)))
    table.add_row("Completed", str(len(state.completed)))
    table.add_row("Failed", str(len(state.failed)))
    table.add_row("Pending", str(len(pending)))
    table.add_row("", "")
    table.add_row("Input Directory", config.paths.input_dir)
    table.add_row("Output Directory", config.paths.output_dir)
    
    console.print(table)
    
    if state.stats['started_at']:
        console.print(f"\n[dim]Started: {state.stats['started_at']}[/dim]")
    if state.stats['last_updated']:
        console.print(f"[dim]Last Updated: {state.stats['last_updated']}[/dim]")


@app.command()
def reset(
    confirm: bool = typer.Option(False, "--yes", help="Skip confirmation prompt")
):
    """
    Reset conversion state (mark all files as pending).
    """
    if not confirm:
        confirm_reset = typer.confirm("Are you sure you want to reset? All progress will be lost.")
        if not confirm_reset:
            console.print("Cancelled.")
            raise typer.Exit()
    
    state = ConversionState()
    state.reset()
    console.print("[green]Conversion state reset. All files will be reprocessed.[/green]")


@app.command()
def clean_output(
    confirm: bool = typer.Option(False, "--yes", help="Skip confirmation prompt")
):
    """
    Clean output directory and reset state.
    """
    if not confirm:
        confirm_clean = typer.confirm("Delete all files in output directory?")
        if not confirm_clean:
            console.print("Cancelled.")
            raise typer.Exit()
    
    config = get_config()
    project_root = get_project_root()
    output_dir = project_root / config.paths.output_dir
    
    import shutil
    if output_dir.exists():
        shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Reset state
    state = ConversionState()
    state.reset()
    
    console.print(f"[green]Output directory cleaned: {output_dir}[/green]")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
