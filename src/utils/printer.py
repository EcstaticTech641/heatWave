"""
Direct Deck Printing Utility.
Provides Windows printer discovery and direct PDF spooling using win32print / win32api.
"""
import os
import sys
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


VIRTUAL_PRINTER_KEYWORDS = [
    "print to pdf",
    "xps document writer",
    "onenote",
    "cutepdf",
    "adobe pdf",
]


def is_virtual_printer(printer_name: str) -> bool:
    """Check if the selected printer is a virtual file-creation driver."""
    if not printer_name:
        return False
    name_lower = printer_name.lower()
    return any(keyword in name_lower for keyword in VIRTUAL_PRINTER_KEYWORDS)


def list_windows_printers() -> Tuple[List[str], str]:
    """
    Enumerate installed local and network Windows printers and identify default printer.

    Returns:
        Tuple of (list_of_printer_names, default_printer_name).
        Returns ([], "") on non-Windows platforms or if win32print fails.
    """
    if sys.platform != "win32":
        logger.info("Direct printing is only supported on Windows operating systems.")
        return [], ""

    try:
        import win32print

        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        printers_raw = win32print.EnumPrinters(flags, None, 2)
        printer_names = [p.get("pPrinterName", "") for p in printers_raw if isinstance(p, dict) and p.get("pPrinterName")]

        # Fallback for tuple structures if returned as tuple
        if not printer_names and printers_raw:
            for p in printers_raw:
                if isinstance(p, (tuple, list)) and len(p) > 2 and isinstance(p[2], str):
                    printer_names.append(p[2])

        default_printer = ""
        try:
            default_printer = win32print.GetDefaultPrinter()
        except Exception as e:
            logger.warning(f"Could not retrieve Windows default printer: {e}")

        if not default_printer and printer_names:
            default_printer = printer_names[0]

        return sorted(list(set(printer_names))), default_printer

    except Exception as e:
        logger.error(f"Error enumerating Windows printers: {e}")
        return [], ""


def print_pdf_file(pdf_path: str, printer_name: str | None = None) -> Tuple[bool, str]:
    """
    Spool a PDF file directly to a specified printer using win32api ShellExecute 'printto'.

    Args:
        pdf_path: Absolute or relative path to the PDF document to print.
        printer_name: Optional target printer name. If None, uses default printer.

    Returns:
        Tuple of (success: bool, status_message: str).
    """
    abs_path = os.path.abspath(pdf_path)
    if not os.path.exists(abs_path):
        return False, f"PDF file not found at path: {abs_path}"

    if sys.platform != "win32":
        return False, "Direct deck printing via win32api is only supported on Windows."

    try:
        import win32print
        import win32api

        target_printer = printer_name
        if not target_printer:
            target_printer = win32print.GetDefaultPrinter()

        if not target_printer:
            return False, "No valid printer target specified and no default printer found."

        # Guard against virtual printers that fail on ShellExecute "printto"
        if is_virtual_printer(target_printer):
            return (
                False,
                f"'{target_printer}' is a virtual file printer and cannot accept silent background spooling. "
                "Please select a physical deck printer, or use the 'Download Heat Sheet PDF' button above."
            )

        # Spool PDF using Windows registered 'printto' verb
        # ShellExecute returns hInstance int > 32 on success
        res = win32api.ShellExecute(
            0,
            "printto",
            abs_path,
            f'"{target_printer}"',
            ".",
            0,
        )

        if isinstance(res, int) and res <= 32:
            return False, f"Windows ShellExecute failed with error code: {res}"

        logger.info(f"Successfully spooled {os.path.basename(abs_path)} to printer '{target_printer}'")
        return True, f"Successfully spooled heat sheet to '{target_printer}'."

    except Exception as e:
        logger.error(f"Failed to spool PDF to printer: {e}")
        return False, f"Printing error: {str(e)}"

