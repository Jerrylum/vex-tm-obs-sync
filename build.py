#!/usr/bin/env python3
"""
Build script for VEX TM OBS Sync executable.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    """Build the executable using PyInstaller."""
    print("Building VEX TM OBS Sync executable...")
    
    # Clean previous builds
    dist_dir = Path("dist")
    build_dir = Path("build")
    
    if dist_dir.exists():
        print("Cleaning previous build artifacts...")
        shutil.rmtree(dist_dir)
    
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    # Build with PyInstaller
    try:
        print("Running PyInstaller...")
        result = subprocess.run([
            "uv", "run", "pyinstaller", 
            "vex-tm-obs-sync.spec"
        ], check=True, capture_output=True, text=True)
        
        print("Build successful!")
        
        # Check if executable was created
        exe_path = dist_dir / "vex-tm-obs-sync.exe"
        if exe_path.exists():
            print(f"Executable created: {exe_path}")
            print(f"File size: {exe_path.stat().st_size / (1024*1024):.1f} MB")
            
            # Copy settings.yml to dist for easy distribution
            settings_src = Path("settings.yml")
            settings_dst = dist_dir / "settings.yml"
            if settings_src.exists():
                shutil.copy2(settings_src, settings_dst)
                print(f"Copied settings.yml to {settings_dst}")
            
            print("\nBuild complete! Files in dist/:")
            for file in dist_dir.iterdir():
                print(f"  - {file.name}")
                
        else:
            print("ERROR: Executable not found after build!")
            sys.exit(1)
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: uv not found. Please install uv first.")
        print("Visit: https://docs.astral.sh/uv/getting-started/installation/")
        sys.exit(1)

if __name__ == "__main__":
    main() 