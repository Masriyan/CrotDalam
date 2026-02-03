#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — CLI Interface
Enhanced command-line interface with Typer.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from crot_dalam import __version__
from crot_dalam.models.data import ScanConfig, InvestigationMode
from crot_dalam.core.scraper import TikTokScraper
from crot_dalam.core.risk_analyzer import RiskAnalyzer

console = Console()

# Banner
BANNER = r"""
   █████████                      █████       ██████████             ████                              
  ███░░░░░███                    ░░███       ░░███░░░░███           ░░███                              
 ███     ░░░  ████████   ██████  ███████      ░███   ░░███  ██████   ░███   ██████   █████████████     
░███         ░░███░░███ ███░░███░░░███░       ░███    ░███ ░░░░░███  ░███  ░░░░░███ ░░███░░███░░███    
░███          ░███ ░░░ ░███ ░███  ░███        ░███    ░███  ███████  ░███   ███████  ░███ ░███ ░███    
░░███     ███ ░███     ░███ ░███  ░███ ███    ░███    ███  ███░░███  ░███  ███░░███  ░███ ░███ ░███    
 ░░█████████  █████    ░░██████   ░░█████     ██████████  ░░████████ █████░░████████ █████░███ █████   
  ░░░░░░░░░  ░░░░░      ░░░░░░     ░░░░░     ░░░░░░░░░░    ░░░░░░░░ ░░░░░  ░░░░░░░░ ░░░░░ ░░░ ░░░░░    
           
v{version} by sudo3rs
""".format(version=__version__)

SUBTITLE = "Collection & Reconnaissance Of TikTok — Discovery, Analysis, Logging, And Monitoring"


def print_banner() -> None:
    """Print the application banner."""
    rprint(
        Panel.fit(
            BANNER,
            title="[bold cyan]CROT DALAM[/]",
            subtitle=f"[dim]{SUBTITLE}[/dim]",
            border_style="cyan",
        )
    )


# Create Typer app
app = typer.Typer(
    name="crot-dalam",
    help="CROT DALAM — TikTok OSINT Tool with Anti-Detection",
    add_completion=False,
)


@app.command()
def search(
    keyword: List[str] = typer.Argument(..., help="Keywords to search (quote phrases)"),
    mode: InvestigationMode = typer.Option(
        InvestigationMode.quick,
        case_sensitive=False,
        help="Investigation mode: quick, moderate, deep, deeper",
    ),
    limit: int = typer.Option(60, min=1, max=1000, help="Max videos per query"),
    out: str = typer.Option("out/crot_dalam", help="Output file basename"),
    headless: bool = typer.Option(True, help="Run browser headlessly"),
    locale: str = typer.Option("en-US", help="Browser locale (e.g., id-ID)"),
    screenshot: bool = typer.Option(False, help="Save screenshots"),
    download: bool = typer.Option(False, help="Download videos via yt-dlp"),
    web_archive: bool = typer.Option(False, "--archive", help="Archive to Archive.today"),
    comments: int = typer.Option(0, min=0, help="Comments to scrape per video"),
    pivot_hashtags: int = typer.Option(0, min=0, help="Auto-search top N hashtags"),
    proxy: Optional[str] = typer.Option(None, help="Proxy URL"),
    user_agent: Optional[str] = typer.Option(None, help="Custom User-Agent"),
    antidetect: bool = typer.Option(True, help="Enable anti-detection"),
    aggressive: bool = typer.Option(False, help="Aggressive anti-detection (slower)"),
):
    """
    Search TikTok for videos matching keywords and extract metadata.
    
    Examples:
        crot-dalam search "undian berhadiah" --mode deep --limit 60
        crot-dalam search "giveaway" "promo gratis" --locale id-ID
    """
    print_banner()
    
    # Build config
    config = ScanConfig(
        keywords=[" ".join(keyword)] if len(keyword) == 1 else list(keyword),
        mode=mode,
        limit=limit,
        headless=headless,
        locale=locale,
        user_agent=user_agent,
        proxy=proxy,
        screenshot=screenshot,
        download=download,
        web_archive=web_archive,
        comments_limit=comments,
        pivot_hashtags=pivot_hashtags,
        antidetect_enabled=antidetect,
        antidetect_aggressive=aggressive,
        output_base=out,
        proxy_list=[proxy] if proxy else [],
    )
    
    # Apply mode presets
    config.apply_mode_presets()
    
    rprint(f"\n[bold]Investigation Mode:[/bold] [cyan]{mode.value}[/cyan]")
    rprint(f"[bold]Keywords:[/bold] {', '.join(config.keywords)}")
    rprint(f"[bold]Limit:[/bold] {limit} videos")
    rprint(f"[bold]Anti-Detection:[/bold] {'Aggressive' if aggressive else 'Enabled' if antidetect else 'Disabled'}")
    rprint()
    
    # Run scan
    try:
        scraper = TikTokScraper(config=config)
        result = scraper.run_scan()
        
        # Print summary
        rprint("\n[bold green]═══ Scan Complete ═══[/bold green]")
        
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")
        
        table.add_row("Total Videos", str(result.total_videos))
        table.add_row("High Risk", f"[red]{result.high_risk_count}[/red]")
        table.add_row("Medium Risk", f"[yellow]{result.medium_risk_count}[/yellow]")
        table.add_row("Duration", f"{result.duration_seconds:.1f}s")
        table.add_row("JSONL", result.output_jsonl or "N/A")
        table.add_row("CSV", result.output_csv or "N/A")
        table.add_row("HTML Report", result.output_html or "N/A")
        
        rprint(table)
        
        if result.errors:
            rprint(f"\n[yellow]Warnings: {len(result.errors)} errors occurred[/yellow]")
        
    except KeyboardInterrupt:
        rprint("\n[red]Interrupted by user[/red]")
        sys.exit(1)
    except Exception as e:
        rprint(f"\n[red]Error: {e}[/red]")
        sys.exit(1)


@app.command()
def gui(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(5000, help="Port to listen on"),
    debug: bool = typer.Option(False, help="Enable debug mode"),
):
    """
    Launch the web GUI dashboard.
    
    The dashboard provides a modern interface for managing investigations.
    """
    print_banner()
    rprint(f"\n[bold cyan]Starting GUI Dashboard...[/bold cyan]")
    rprint(f"[dim]Open http://{host}:{port} in your browser[/dim]\n")
    
    from crot_dalam.gui import run_gui
    run_gui(host=host, port=port, debug=debug)


@app.command()
def analyze(
    text: str = typer.Argument(..., help="Text to analyze for risk"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed matches"),
):
    """
    Analyze text for scam/phishing risk indicators.
    
    Example:
        crot-dalam analyze "Transfer dulu untuk klaim hadiah undian"
    """
    analyzer = RiskAnalyzer()
    result = analyzer.analyze(text)
    
    # Risk level colors
    level_colors = {
        "NONE": "green",
        "LOW": "green",
        "MEDIUM": "yellow",
        "HIGH": "red",
        "CRITICAL": "bold red",
    }
    
    color = level_colors.get(result.level.name, "white")
    
    rprint(f"\n[bold]Risk Score:[/bold] [{color}]{result.score}[/{color}]")
    rprint(f"[bold]Risk Level:[/bold] [{color}]{result.level.name}[/{color}]")
    
    if result.matches:
        rprint(f"\n[bold]Matches ({len(result.matches)}):[/bold]")
        for match in result.matches:
            rprint(f"  • {match.term} [dim]({match.category}, {match.language})[/dim]")
    
    if result.extracted_entities and verbose:
        rprint("\n[bold]Extracted Entities:[/bold]")
        for entity_type, values in result.extracted_entities.items():
            rprint(f"  {entity_type}: {', '.join(values)}")


@app.command()
def version():
    """Show version information."""
    rprint(f"CROT DALAM v{__version__}")


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
