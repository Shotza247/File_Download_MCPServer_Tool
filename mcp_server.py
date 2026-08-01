from mcp.server import MCPServer
from pathlib import Path
from typing import TypedDict
import logging
import sys


SERVER_NAME = "startup-mcp-server"
OUTPUT_DIRECTORY = (Path.cwd() / "generated_files").resolve()

mcp = MCPServer(SERVER_NAME)
logger = logging.getLogger(SERVER_NAME)


class FileCreationResult(TypedDict):
    success: bool
    message: str
    file_path: str
    characters_written: int
    error: str


def configure_logging(level: int = logging.INFO) -> None:
    """Configure application logging.

    Logs are written to stderr because stdout is used by the MCP
    stdio transport for protocol communication.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        stream=sys.stderr,
    )


def resolve_safe_path(file_name: str) -> Path:
    """Resolve a filename inside the configured output directory.

    Prevents paths such as '../../important-file.txt' from escaping
    the generated-files directory.
    """
    cleaned_name = file_name.strip()

    if not cleaned_name:
        raise ValueError("The file name cannot be empty.")

    target_path = (OUTPUT_DIRECTORY / cleaned_name).resolve()

    try:
        target_path.relative_to(OUTPUT_DIRECTORY)
    except ValueError as exc:
        raise ValueError(
            "The requested file must remain inside the output directory."
        ) from exc

    return target_path


def write_text_file(
    file_name: str,
    content: str,
    *,
    overwrite: bool = False,
) -> tuple[Path, int]:
    """Write text to a file and return its path and character count.

    This function contains no MCP-specific logic, so it can be reused
    elsewhere and tested independently.
    """
    target_path = resolve_safe_path(file_name)

    # Support names such as reports/daily-report.txt.
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # "x" fails when the file exists, while "w" overwrites it.
    mode = "w" if overwrite else "x"

    with target_path.open(
        mode=mode,
        encoding="utf-8",
        newline="",
    ) as file:
        characters_written = file.write(content)

    return target_path, characters_written


@mcp.tool()
def create_file(
    file_name: str,
    content: str,
    overwrite: bool = False,
) -> FileCreationResult:
    """Create a UTF-8 text file in the generated_files directory.

    Args:
        file_name:
            File name or relative path, such as "notes.txt" or
            "reports/summary.txt".

        content:
            Text to write to the file.

        overwrite:
            Whether an existing file may be replaced. Defaults to False.

    Returns:
        A structured result describing whether the operation succeeded.
    """
    logger.info(
        "File creation requested: file_name=%r overwrite=%s",
        file_name,
        overwrite,
    )

    try:
        file_path, characters_written = write_text_file(
            file_name=file_name,
            content=content,
            overwrite=overwrite,
        )

    except ValueError as exc:
        logger.warning(
            "File creation rejected: file_name=%r reason=%s",
            file_name,
            exc,
        )

        return {
            "success": False,
            "message": "The file request was invalid.",
            "file_path": "",
            "characters_written": 0,
            "error": str(exc),
        }

    except FileExistsError:
        logger.warning(
            "File already exists and overwrite is disabled: file_name=%r",
            file_name,
        )

        return {
            "success": False,
            "message": "The file already exists.",
            "file_path": "",
            "characters_written": 0,
            "error": "Set overwrite to true to replace the existing file.",
        }

    except PermissionError as exc:
        logger.error(
            "Permission denied while creating file: file_name=%r",
            file_name,
        )

        return {
            "success": False,
            "message": "Permission was denied while creating the file.",
            "file_path": "",
            "characters_written": 0,
            "error": str(exc),
        }

    except OSError as exc:
        logger.exception(
            "Operating-system error while creating file: file_name=%r",
            file_name,
        )

        return {
            "success": False,
            "message": "An operating-system error occurred.",
            "file_path": "",
            "characters_written": 0,
            "error": str(exc),
        }

    logger.info(
        "File created successfully: path=%s characters_written=%d",
        file_path,
        characters_written,
    )

    return {
        "success": True,
        "message": "File created successfully.",
        "file_path": str(file_path),
        "characters_written": characters_written,
        "error": "",
    }


def main() -> None:
    """Configure and start the MCP server."""
    configure_logging()

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Starting MCP server: name=%s output_directory=%s",
        SERVER_NAME,
        OUTPUT_DIRECTORY,
    )

    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by the user.")
    except Exception:
        logger.exception("MCP server stopped unexpectedly.")
        raise


if __name__ == "__main__":
    main()