import os
import datetime
import sys
import argparse
import json
import re
from pathlib import Path

# Script info
__author__ = "Sajeeva SA"
__version__ = "1.0.0"

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import exifread
    EXIFREAD_AVAILABLE = True
except ImportError:
    EXIFREAD_AVAILABLE = False

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    # Fallback: define dummy color constants
    class Fore:
        RED = ''
        GREEN = ''
        YELLOW = ''
        CYAN = ''
        MAGENTA = ''
        WHITE = ''
        RESET = ''
    class Style:
        BRIGHT = ''
        RESET_ALL = ''

# Supported image extensions
IMAGE_EXTENSIONS = {
    # Common formats (Pillow)
    '.jpg', '.jpeg', '.png', '.tiff', '.tif',
    # RAW formats (exifread)
    '.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2', '.pef', '.srw', '.raf'
}

# Global options
verbose_mode = False
dry_run_mode = False
safe_mode = False
log_mode = False
log_file_path = None


def print_verbose(message):
    """Print message only in verbose mode."""
    if verbose_mode:
        print(f"{Fore.CYAN}[VERBOSE]{Style.RESET_ALL} {message}")


def print_success(message):
    """Print success message in green."""
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")


def print_warning(message):
    """Print warning message in yellow."""
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")


def print_error(message):
    """Print error message in red."""
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")


def print_mismatch(message):
    """Print mismatch message in magenta (highlighted)."""
    print(f"{Fore.MAGENTA}{Style.BRIGHT}[MISMATCH]{Style.RESET_ALL} {message}")


def print_match(message):
    """Print match message in green."""
    print(f"{Fore.GREEN}[MATCH]{Style.RESET_ALL} {message}")


def is_image_file(filepath):
    """Check if file is a supported image format."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in IMAGE_EXTENSIONS


def read_date_taken(filepath):
    """
    Extract 'Date Taken' (DateTimeOriginal) from image EXIF metadata.
    Returns datetime object or None if not found.
    """
    filepath = os.path.normpath(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    
    # Try exifread first (better for RAW files)
    if EXIFREAD_AVAILABLE:
        try:
            with open(filepath, 'rb') as f:
                tags = exifread.process_file(f, details=False, stop_tag='EXIF DateTimeOriginal')
                if 'EXIF DateTimeOriginal' in tags:
                    date_str = str(tags['EXIF DateTimeOriginal'])
                    return datetime.datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
        except Exception as e:
            print_verbose(f"exifread failed for {filepath}: {e}")
    
    # Try Pillow as fallback (good for JPEG/PNG/TIFF)
    if PIL_AVAILABLE and ext in {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}:
        try:
            with Image.open(filepath) as img:
                exif_data = img._getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == 'DateTimeOriginal':
                            return datetime.datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
        except Exception as e:
            print_verbose(f"Pillow failed for {filepath}: {e}")
    
    return None


def parse_filename_date(filename):
    """
    Parse date/time from filename.
    Supports formats like:
    - 2026-01-20 14-30-00.jpg
    - 2026-01-20_14-30-00.jpg
    - 2026-01-20 14.30.00.jpg (dots as time separators)
    - 2026-01-20 14.30.00-3.jpg (with suffix after seconds - ignored)
    - 20260120_143000.jpg
    - 2026-01-20.jpg (date only)
    Returns datetime object or None if not parseable.
    """
    basename = os.path.splitext(os.path.basename(filename))[0]
    
    # Pattern: YYYY-MM-DD HH-MM-SS or YYYY-MM-DD_HH-MM-SS or YYYY-MM-DD HH.MM.SS
    # Time separators can be - or . 
    # Anything after the seconds (like -3, -1) is ignored
    pattern1 = r'^(\d{4})-(\d{2})-(\d{2})[\s_](\d{2})[-.](\d{2})[-.](\d{2})'
    match = re.match(pattern1, basename)
    if match:
        y, m, d, h, mi, s = map(int, match.groups())
        try:
            return datetime.datetime(y, m, d, h, mi, s)
        except ValueError:
            pass
    
    # Pattern: YYYYMMDD_HHMMSS
    pattern2 = r'^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})'
    match = re.match(pattern2, basename)
    if match:
        y, m, d, h, mi, s = map(int, match.groups())
        try:
            return datetime.datetime(y, m, d, h, mi, s)
        except ValueError:
            pass
    
    # Pattern: YYYY-MM-DD (date only, must be end of filename)
    pattern3 = r'^(\d{4})-(\d{2})-(\d{2})$'
    match = re.match(pattern3, basename)
    if match:
        y, m, d = map(int, match.groups())
        try:
            return datetime.datetime(y, m, d, 0, 0, 0)
        except ValueError:
            pass
    
    return None


def check_mismatch(filepath, tolerance_seconds=2):
    """
    Compare filename date with EXIF metadata date.
    Returns tuple: (has_mismatch, filename_date, exif_date)
    """
    filename_date = parse_filename_date(filepath)
    exif_date = read_date_taken(filepath)
    
    if filename_date is None or exif_date is None:
        return (None, filename_date, exif_date)  # Can't compare
    
    diff = abs((filename_date - exif_date).total_seconds())
    has_mismatch = diff > tolerance_seconds
    
    return (has_mismatch, filename_date, exif_date)


def get_unique_filename(directory, base_name, extension):
    """
    Get unique filename with counter suffix if collision exists.
    Returns the full path with unique name.
    """
    new_path = os.path.join(directory, base_name + extension)
    
    if not os.path.exists(new_path):
        return new_path
    
    # Add counter suffix
    counter = 1
    while True:
        new_name = f"{base_name}_{counter:03d}{extension}"
        new_path = os.path.join(directory, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1
        if counter > 9999:
            raise Exception("Too many files with same timestamp")


def log_rename(original_path, new_path):
    """Append rename operation to JSON log file."""
    global log_file_path
    
    if not log_mode:
        return
    
    log_entry = {
        "original": os.path.abspath(original_path),
        "renamed": os.path.abspath(new_path),
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # Read existing log or create new
    log_data = []
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            log_data = []
    
    log_data.append(log_entry)
    
    with open(log_file_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    print_verbose(f"Logged rename: {original_path} -> {new_path}")


def rename_file_by_date(filepath, use_metadata=False):
    """
    Rename file by date (modified date or metadata date).
    Handles collision and logging based on global options.
    """
    filepath = os.path.normpath(filepath)
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    extension = os.path.splitext(filename)[1]
    
    # Skip the script itself
    if filepath == os.path.abspath(__file__):
        print_verbose('Skipping the script itself.')
        return
    
    if not os.path.exists(filepath):
        print_error(f'Path not found: {filepath}')
        return
    
    if not os.path.isfile(filepath):
        return  # Skip directories
    
    # Get the date to use
    if use_metadata:
        if not is_image_file(filepath):
            print_verbose(f'Skipping non-image file: {filename}')
            return
        
        target_date = read_date_taken(filepath)
        if target_date is None:
            print_warning(f'No Date Taken found for: {filename}')
            return
        date_source = "Date Taken"
    else:
        modified_time = os.path.getmtime(filepath)
        target_date = datetime.datetime.fromtimestamp(modified_time)
        date_source = "modified"
    
    # Create new filename
    base_name = target_date.strftime('%Y-%m-%d %H-%M-%S')
    
    if safe_mode:
        new_path = get_unique_filename(directory, base_name, extension)
    else:
        new_path = os.path.join(directory, base_name + extension)
        if os.path.exists(new_path) and new_path != filepath:
            print_warning(f'Collision: {new_path} already exists. Skipping {filename}')
            return
    
    # Skip if same path
    if os.path.normpath(new_path) == os.path.normpath(filepath):
        print_verbose(f'Already named correctly: {filename}')
        return
    
    # Perform or preview rename
    if dry_run_mode:
        print(f"{Fore.CYAN}[DRY-RUN]{Style.RESET_ALL} Would rename: {filename} -> {os.path.basename(new_path)} ({date_source} date)")
    else:
        os.rename(filepath, new_path)
        log_rename(filepath, new_path)
        print_success(f'Renamed: {filename} -> {os.path.basename(new_path)} ({date_source} date)')


def process_path(filepath, action='modified'):
    """
    Process a file or directory.
    action: 'modified', 'metadata', or 'check'
    """
    filepath = os.path.normpath(filepath)
    
    if not os.path.exists(filepath):
        print_error(f'Path not found: {filepath}')
        return
    
    if os.path.isfile(filepath):
        if action == 'check':
            check_and_report_file(filepath)
        else:
            rename_file_by_date(filepath, use_metadata=(action == 'metadata'))
    else:
        # Directory: process all files recursively
        files_processed = 0
        mismatches_found = 0
        
        for root, _, files in os.walk(filepath):
            for file in files:
                full_path = os.path.join(root, file)
                
                if action == 'check':
                    if is_image_file(full_path):
                        result = check_and_report_file(full_path)
                        files_processed += 1
                        if result:
                            mismatches_found += 1
                else:
                    if action == 'metadata' and not is_image_file(full_path):
                        continue
                    rename_file_by_date(full_path, use_metadata=(action == 'metadata'))
                    files_processed += 1
        
        if action == 'check':
            print(f"\n{Style.BRIGHT}Summary:{Style.RESET_ALL}")
            print(f"  Images checked: {files_processed}")
            print(f"  Mismatches found: {Fore.MAGENTA}{mismatches_found}{Style.RESET_ALL}" if mismatches_found > 0 
                  else f"  Mismatches found: {Fore.GREEN}0{Style.RESET_ALL}")


def check_and_report_file(filepath):
    """Check single file for mismatch and report. Returns True if mismatch found."""
    if not is_image_file(filepath):
        return False
    
    filename = os.path.basename(filepath)
    has_mismatch, filename_date, exif_date = check_mismatch(filepath)
    
    if has_mismatch is None:
        if exif_date is None:
            print_warning(f'{filename}: No Date Taken found in metadata')
        elif filename_date is None:
            print_verbose(f'{filename}: Cannot parse date from filename')
        return False
    
    if has_mismatch:
        print_mismatch(f'{filename}')
        print(f"    Filename date: {filename_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Date Taken:    {exif_date.strftime('%Y-%m-%d %H:%M:%S')}")
        return True
    else:
        if verbose_mode:
            print_match(f'{filename} (dates match)')
        return False


def interactive_menu(target_path):
    """Display interactive menu and handle user choices."""
    global verbose_mode, dry_run_mode, safe_mode, log_mode, log_file_path
    
    while True:
        print(f"\n{Style.BRIGHT}=== Image File Renamer ==={Style.RESET_ALL}")
        print(f"by {Fore.CYAN}{__author__}{Style.RESET_ALL}")
        print(f"\nTarget: {Fore.CYAN}{target_path}{Style.RESET_ALL}")
        print(f"\nOptions:")
        print(f"  {Fore.WHITE}1.{Style.RESET_ALL} Rename files by modified date")
        print(f"  {Fore.WHITE}2.{Style.RESET_ALL} Check Date Taken vs filename mismatches")
        print(f"  {Fore.WHITE}3.{Style.RESET_ALL} Rename files by Date Taken")
        print(f"  {Fore.WHITE}4.{Style.RESET_ALL} Toggle settings")
        print(f"  {Fore.WHITE}5.{Style.RESET_ALL} Exit")
        
        print(f"\n{Style.BRIGHT}Current settings:{Style.RESET_ALL}")
        print(f"  Dry-run: {Fore.GREEN if dry_run_mode else Fore.RED}{dry_run_mode}{Style.RESET_ALL}")
        print(f"  Safe mode (collision handling): {Fore.GREEN if safe_mode else Fore.RED}{safe_mode}{Style.RESET_ALL}")
        print(f"  Logging: {Fore.GREEN if log_mode else Fore.RED}{log_mode}{Style.RESET_ALL}")
        print(f"  Verbose: {Fore.GREEN if verbose_mode else Fore.RED}{verbose_mode}{Style.RESET_ALL}")
        
        try:
            choice = input(f"\n{Fore.YELLOW}Enter choice (1-5): {Style.RESET_ALL}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        
        if choice == '1':
            print(f"\n{Style.BRIGHT}Renaming by modified date...{Style.RESET_ALL}\n")
            process_path(target_path, action='modified')
        elif choice == '2':
            print(f"\n{Style.BRIGHT}Checking for mismatches...{Style.RESET_ALL}\n")
            process_path(target_path, action='check')
        elif choice == '3':
            print(f"\n{Style.BRIGHT}Renaming by Date Taken...{Style.RESET_ALL}\n")
            process_path(target_path, action='metadata')
        elif choice == '4':
            toggle_settings_menu()
        elif choice == '5':
            print("Exiting...")
            break
        else:
            print_error("Invalid choice. Please enter 1-5.")


def toggle_settings_menu():
    """Sub-menu for toggling settings."""
    global verbose_mode, dry_run_mode, safe_mode, log_mode
    
    while True:
        print(f"\n{Style.BRIGHT}=== Settings ==={Style.RESET_ALL}")
        print(f"  {Fore.WHITE}1.{Style.RESET_ALL} Toggle Dry-run (currently: {dry_run_mode})")
        print(f"  {Fore.WHITE}2.{Style.RESET_ALL} Toggle Safe mode (currently: {safe_mode})")
        print(f"  {Fore.WHITE}3.{Style.RESET_ALL} Toggle Logging (currently: {log_mode})")
        print(f"  {Fore.WHITE}4.{Style.RESET_ALL} Toggle Verbose (currently: {verbose_mode})")
        print(f"  {Fore.WHITE}5.{Style.RESET_ALL} Back to main menu")
        
        try:
            choice = input(f"\n{Fore.YELLOW}Enter choice (1-5): {Style.RESET_ALL}").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if choice == '1':
            dry_run_mode = not dry_run_mode
            print_success(f"Dry-run mode: {dry_run_mode}")
        elif choice == '2':
            safe_mode = not safe_mode
            print_success(f"Safe mode: {safe_mode}")
        elif choice == '3':
            log_mode = not log_mode
            print_success(f"Logging: {log_mode}")
        elif choice == '4':
            verbose_mode = not verbose_mode
            print_success(f"Verbose mode: {verbose_mode}")
        elif choice == '5':
            break
        else:
            print_error("Invalid choice.")


def main():
    global verbose_mode, dry_run_mode, safe_mode, log_mode, log_file_path
    
    # Show credit
    print(f"\n{Style.BRIGHT}Image File Renamer v{__version__}{Style.RESET_ALL} by {Fore.CYAN}{__author__}{Style.RESET_ALL}\n")
    
    parser = argparse.ArgumentParser(
        description='Rename image files by date (modified date or Date Taken from metadata)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python filerename.py -c "C:\\Photos"           Check mismatches
  python filerename.py -r -d "C:\\Photos"        Dry-run metadata rename
  python filerename.py -r -s -l "C:\\Photos"     Safe rename with logging
  python filerename.py -m -v "C:\\Photos"        Verbose modified-date rename
  python filerename.py "C:\\Photos"              Interactive menu
        """
    )
    
    # Action flags (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument('-m', '--modified', action='store_true',
                              help='Rename files by modified date')
    action_group.add_argument('-c', '--check', action='store_true',
                              help='Check and report Date Taken vs filename mismatches')
    action_group.add_argument('-r', '--rename-meta', action='store_true',
                              help='Rename files by Date Taken from metadata')
    action_group.add_argument('-i', '--interactive', action='store_true',
                              help='Launch interactive menu (default if no action specified)')
    
    # Option flags
    parser.add_argument('-d', '--dry-run', action='store_true',
                        help='Preview changes without actually renaming')
    parser.add_argument('-s', '--safe', action='store_true',
                        help='Add counter suffix on name collision (e.g., _001)')
    parser.add_argument('-l', '--log', action='store_true',
                        help='Save rename operations to rename_log.json')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show detailed output')
    
    # Path argument
    parser.add_argument('path', nargs='?', default=None,
                        help='File or directory path to process')
    
    args = parser.parse_args()
    
    # Set global options
    verbose_mode = args.verbose
    dry_run_mode = args.dry_run
    safe_mode = args.safe
    log_mode = args.log
    
    # Check dependencies
    if not PIL_AVAILABLE and not EXIFREAD_AVAILABLE:
        print_warning("Neither Pillow nor exifread is installed. EXIF reading will not work.")
        print("Install dependencies: pip install -r requirements.txt")
    
    # Get target path
    if args.path:
        target_path = os.path.normpath(args.path)
    else:
        print_error("Please provide a file or directory path.")
        parser.print_help()
        sys.exit(1)
    
    # Set log file path
    if os.path.isdir(target_path):
        log_file_path = os.path.join(target_path, 'rename_log.json')
    else:
        log_file_path = os.path.join(os.path.dirname(target_path), 'rename_log.json')
    
    # Execute action
    if args.modified:
        print_verbose("Mode: Rename by modified date")
        process_path(target_path, action='modified')
    elif args.check:
        print_verbose("Mode: Check mismatches")
        process_path(target_path, action='check')
    elif args.rename_meta:
        print_verbose("Mode: Rename by Date Taken")
        process_path(target_path, action='metadata')
    else:
        # Default to interactive mode
        interactive_menu(target_path)


if __name__ == '__main__':
    main()
