from MediaProcessor import MediaProcessor
from pathlib import Path
import configparser

base_dir = Path(__file__).resolve().parent

config_path = base_dir / 'settings.ini'
config = configparser.ConfigParser()
config.read(config_path)

# Replace this with your source directory path
source_directory = config.get('files', 'source_dir')
output_dir = config.get('files', 'output_dir')

max_dir_size_gb = config.getfloat('settings', 'max_dir_size_gb')
quality = config.getint('settings', 'quality')


processor = MediaProcessor(source_dir=source_directory, output_dir=output_dir)
# Quality set to 85% compression. i.e. 100% down to 85%, max output size = total output in GB
processor.process_images(quality=quality, max_dir_size_gb=max_dir_size_gb)