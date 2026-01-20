# Image File Renamer

A Python utility to rename image files based on their dates. Supports renaming by file modified date or EXIF metadata (Date Taken), with options for collision handling, dry-run previews, and operation logging.

## Features

- **Rename by Modified Date** - Rename files using their filesystem modified timestamp
- **Rename by Date Taken** - Extract and use EXIF DateTimeOriginal metadata
- **Mismatch Detection** - Compare filename dates with EXIF metadata to find discrepancies
- **Collision Handling** - Safe mode adds counter suffixes (e.g., `_001`) to prevent overwrites
- **Dry-Run Mode** - Preview changes before applying them
- **Operation Logging** - Save all rename operations to a JSON log file
- **Interactive Menu** - User-friendly menu for easy operation
- **RAW Format Support** - Works with CR2, CR3, NEF, ARW, DNG, and other RAW formats

## Supported Formats

| Type | Extensions |
|------|------------|
| Common | `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif` |
| RAW | `.cr2`, `.cr3`, `.nef`, `.arw`, `.dng`, `.orf`, `.rw2`, `.pef`, `.srw`, `.raf` |

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/saj82/Image-file-renamer.git
   cd Image-file-renamer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Interactive Mode

Launch the interactive menu by providing a path:

```bash
python filerename.py "C:\Photos"
```

### Command Line Options

```
usage: filerename.py [-h] [-m | -c | -r | -i] [-d] [-s] [-l] [-v] [path]

Rename image files by date (modified date or Date Taken from metadata)

positional arguments:
  path                  File or directory path to process

optional arguments:
  -h, --help            show this help message and exit
  -m, --modified        Rename files by modified date
  -c, --check           Check and report Date Taken vs filename mismatches
  -r, --rename-meta     Rename files by Date Taken from metadata
  -i, --interactive     Launch interactive menu (default)
  -d, --dry-run         Preview changes without actually renaming
  -s, --safe            Add counter suffix on name collision (e.g., _001)
  -l, --log             Save rename operations to rename_log.json
  -v, --verbose         Show detailed output
```

### Examples

```bash
# Check for date mismatches between filenames and EXIF data
python filerename.py -c "C:\Photos"

# Dry-run: preview what would be renamed using metadata
python filerename.py -r -d "C:\Photos"

# Rename with safe mode (collision handling) and logging
python filerename.py -r -s -l "C:\Photos"

# Rename by modified date with verbose output
python filerename.py -m -v "C:\Photos"

# Interactive menu
python filerename.py "C:\Photos"
```

## Output Format

Files are renamed to the format: `YYYY-MM-DD HH-MM-SS.ext`

Example: `2024-03-15 14-30-45.jpg`

When safe mode is enabled and a collision occurs, a counter is appended: `2024-03-15 14-30-45_001.jpg`

## Dependencies

- **Pillow** - For reading EXIF from JPEG/PNG/TIFF files
- **exifread** - For reading EXIF from RAW files
- **colorama** - For colored terminal output (optional, gracefully degrades)

## License

MIT License

## Author

Sajeeva SA
