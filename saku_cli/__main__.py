import typer
from rich.console import Console
from rich.progress import Progress
from rich.syntax import Syntax

from saku_cli.api import clone_request, index_request, search_request
from saku_cli.utils import find_matching_lines

# COLORS
BLACK = "#000000"
BRIGHT_RED = "#ef2929"
MONOKAI_BG = "#272822"

console = Console()
app = typer.Typer()


@app.command()
def clone(url: str):
    console.print(f"Cloning {url}")
    with Progress(transient=True) as progress:
        progress.add_task("Clone", start=False, total=None)
        clone_request(url)
    console.print(f"Cloned {url}!")


@app.command()
def index():
    console.print(f"Indexing...")
    with Progress(transient=True) as progress:
        progress.add_task("Index", start=False, total=None)
        index_request()
    console.print(f"Indexing Complete!")


@app.command()
def search(
    regex: str,
    skip: int = 0,
    limit: int = 5,
    case_sensitive: bool = True,
    size_lt: int = -1,
    size_gt: int = -1,
    path_like: str = "",
):
    response = search_request(regex, skip, limit, case_sensitive, size_lt, size_gt, path_like)
    matches = response["matches"]
    console.print(f"Found {response['total']} matching files")
    console.print(f"Skipping {response['skip']} files and limiting to {min(response['limit'], len(matches))} results")

    for i, (file, content) in enumerate(matches.items()):
        header_line = f"\nFile: {i + 1} {file}"
        header_line += " " * (console.width - len(header_line) + 1)
        console.print(header_line, style=f"bold {BRIGHT_RED} on {BLACK}")

        printed_first_block = False
        line_ranges = find_matching_lines(regex, content)
        for start_line, end_line, matched_lines in line_ranges:
            if printed_first_block:
                console.print("." * console.width, style=f"on {MONOKAI_BG}")
            else:
                printed_first_block = True

            actual_range = max(start_line - 4, 0), end_line + 4

            lexer = Syntax.guess_lexer(file, content)
            syntax = Syntax(
                content,
                lexer,
                line_numbers=True,
                highlight_lines=matched_lines,
                line_range=actual_range,
                theme="monokai",
            )
            console.print(syntax)


if __name__ == "__main__":
    app()
