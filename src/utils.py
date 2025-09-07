from rich.console import Console
from rich.table import Table
import logging

_console = Console()

def get_logger(name: str = "wildlife"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def banner(title: str):
    _console.rule(f"[bold green]{title}[/bold green]")
