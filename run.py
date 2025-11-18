from MediaProcessor import MediaProcessor
from pathlib import Path
import configparser
import sys
import os


def get_app_base_dir() -> Path:
	"""Return the directory the app is running from.

	When running as a bundled executable (PyInstaller, cx_Freeze, etc.) use
	the executable location. Otherwise use the script file location.
	This ensures `settings.ini` placed next to the exe is found.
	"""
	# PyInstaller and similar set ``sys.frozen`` when bundled.
	if getattr(sys, "frozen", False):
		return Path(sys.executable).resolve().parent
	return Path(__file__).resolve().parent


base_dir = get_app_base_dir()

config_path = base_dir / 'settings.ini'
config = configparser.ConfigParser()

# If the config isn't next to the exe/script, try a couple of reasonable
# fallbacks: current working directory and PyInstaller's _MEIPASS.
if not config_path.exists():
	alt_cwd = Path(os.getcwd()) / 'settings.ini'
	if alt_cwd.exists():
		config_path = alt_cwd
	else:
		meipass = getattr(sys, '_MEIPASS', None)
		if meipass:
			meipass_candidate = Path(meipass) / 'settings.ini'
			if meipass_candidate.exists():
				config_path = meipass_candidate

if not config_path.exists():
	raise SystemExit(f"settings.ini not found. Looked in: {base_dir}, cwd: {os.getcwd()}")

config.read(config_path)

# Replace this with your source directory path
source_directory = config.get('files', 'source_dir')
output_dir = config.get('files', 'output_dir')

max_dir_size_gb = config.getfloat('settings', 'max_dir_size_gb')
quality = config.getint('settings', 'quality')


processor = MediaProcessor(source_dir=source_directory, output_dir=output_dir)
# Quality set to 85% compression. i.e. 100% down to 85%, max output size = total output in GB
processor.process_images(quality=quality, max_dir_size_gb=max_dir_size_gb)