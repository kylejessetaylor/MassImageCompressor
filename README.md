# Build
Build found under dist/
Must have the run.exe & settings.ini file in same dir to run.
Set up the values in the settings file before running. Specifically the:
  source_dir
  output_dir
Other settings (max_dir_size_gb & quality) are optional.

# Code
How the code works.
## Logic
Select a random subset of images (across nested folders) within the source_dir whose compressed total size does not exceed max_dir_size_gb, then write them into output_dir with filenames prefixed by a sequential count and folder name: "count_foldername_filename" so that the files retain the order which they had in the source_dir
