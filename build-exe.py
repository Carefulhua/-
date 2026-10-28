#!/usr/bin/env python3
"""Build invoice-renamer.exe using PyInstaller.

Usage:
    python build-exe.py
"""
import os
import shutil
import subprocess
import sys
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

BUILD_FILE = os.path.join(SCRIPT_DIR, "invoice-renamer.py")
OUTPUT_EXE = os.path.join(SCRIPT_DIR, "invoice-renamer.exe")


def main():
    print("=" * 48)
    print("   Invoice PDF Renamer - Build EXE")
    print("=" * 48)
    print(f"  Platform: {platform.system()} {platform.release()}")
    print(f"  Directory: {SCRIPT_DIR}")
    print()

    # Sanity check: refuse to run from C:\Windows
    cwd = os.path.abspath(".").upper()
    if cwd.startswith("C:\\WINDOWS") or cwd == "C:\\":
        print("ERROR: Current directory is C:\\Windows.")
        print("This script cannot run from the Windows system directory.")
        print("Please run from the correct folder (发票).")
        print(f"Script location: {SCRIPT_DIR}")
        sys.exit(1)

    # Check source file exists
    if not os.path.exists(BUILD_FILE):
        print(f"ERROR: {BUILD_FILE} not found.")
        print("Make sure build-exe.py is in the same directory as invoice-renamer.py.")
        sys.exit(1)

    # Ensure dependencies installed
    print("Checking dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pypdf", "pyinstaller", "--quiet"],
        check=True,
    )
    print("Dependencies installed.")
    print()

    # Clean old build artifacts
    print("Cleaning old build artifacts...")
    for d in ["build", "dist"]:
        p = os.path.join(SCRIPT_DIR, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
    for f in ["invoice-renamer.spec"]:
        p = os.path.join(SCRIPT_DIR, f)
        if os.path.isfile(p):
            os.remove(p)
    print("Done.")
    print()

    # Build EXE
    print("Building EXE, this may take a few minutes...")
    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--collect-all", "pypdf",
            "--name", "invoice-renamer",
            "--distpath", SCRIPT_DIR,
            BUILD_FILE,
        ],
        cwd=SCRIPT_DIR,
    )

    if result.returncode != 0:
        print()
        print("=" * 48)
        print("   Build failed!")
        print("=" * 48)
        print()
        print("Try manually:")
        print(f"  cd {SCRIPT_DIR}")
        print("  pip install pypdf pyinstaller")
        print("  pyinstaller --onefile --collect-all pypdf --name invoice-renamer --distpath . invoice-renamer.py")
        sys.exit(1)

    # Verify output
    if os.path.exists(OUTPUT_EXE):
        size = os.path.getsize(OUTPUT_EXE)
        print()
        print("=" * 48)
        print("   Build successful!")
        print(f"   EXE: {OUTPUT_EXE}")
        print(f"   Size: {size / 1024 / 1024:.1f} MB")
        print("=" * 48)
        print()
        print("Usage: invoice-renamer.exe \"C:\\path\\to\\invoices\"")
    else:
        print("Build completed but invoice-renamer.exe not found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
