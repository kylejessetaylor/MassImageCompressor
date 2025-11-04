import io
import os
import random
from PIL import Image
from typing import List, Tuple


class MediaProcessor:
    def __init__(self, source_dir: str, output_dir: str):
        self.source_dir = source_dir
        self.output_dir = output_dir
        # Supported image formats (lowercase)
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
        # Create compressed folder at specific output dir
        self.compressed_dir = os.path.join(self.output_dir, "compressed")
        if not os.path.exists(self.compressed_dir):
            os.makedirs(self.compressed_dir)

    def gather_all_images(self) -> List[str]:
        """Recursively walk `self.source_dir` and return a list of image file paths."""
        images: List[str] = []
        for root, _, files in os.walk(self.source_dir):
            for name in files:
                _, ext = os.path.splitext(name)
                if ext.lower() in self.image_extensions:
                    images.append(os.path.join(root, name))
        return images

    def compress_image_to_bytes(self, image_path: str, quality: float) -> bytes:
        """
        Compress an image to an in-memory JPEG and return bytes.

        `quality` may be a float (e.g. 15.5); it will be rounded to an
        integer when passed to the JPEG encoder. We convert outputs to
        JPEG for predictable size control; transparency is flattened to
        a white background. If you need PNG transparency preserved, we
        can add an option later.
        """
        with Image.open(image_path) as img:
            # Convert transparency to white background when needed
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            else:
                # Ensure RGB for JPEG
                img = img.convert('RGB')

            buf = io.BytesIO()
            # Save as JPEG to get consistent quality control. PIL expects an
            # integer quality; allow the caller to pass a float and round it.
            quality_int = int(round(float(quality)))
            # clamp to reasonable JPEG quality range 1-95
            quality_int = max(1, min(95, quality_int))
            img.save(buf, format='JPEG', quality=quality_int, optimize=True)
            return buf.getvalue()

    def choose_random_subset_by_size(self, max_dir_size_gb: float, quality: float) -> Tuple[List[Tuple[str,int]], List[Tuple[str,int]]]:
        """
        Fast heuristic selection: use file sizes and a compression_factor
        to estimate compressed size, then randomly pick files until the
        estimated total fits within `max_dir_size_gb`.

        Returns (chosen_paths, remaining_paths).
        """
        all_images = self.gather_all_images()
        if not all_images:
            return [], []

        print("Gathering file information...", end="\r")

        image_sizes: List[Tuple[str, int]] = []
        processed = 0
        total_images = len(all_images)

        # Heuristic compression factor: lower quality => smaller compressed size
        # quality/300 gives ~0.25 at quality=75, ~=0.05 at quality=15
        compression_factor = max(0.01, float(quality) / 300.0)
        max_bytes = int(max_dir_size_gb * 1024 ** 3)

        for path in all_images:
            processed += 1
            try:
                size = os.path.getsize(path)
                image_sizes.append((path, size))
                status = f"Scanning: {processed}/{total_images} images"
                print(status + " " * 20, end="\r")
            except Exception:
                continue

        # Print a persistent scanned summary line (so it remains above later updates)
        print(f"Scanned: {processed}/{total_images} images")
        print(f"Selecting random subset to fit within {max_dir_size_gb}GB...", end="\r")

        random.shuffle(image_sizes)
        chosen_paths: List[Tuple[str,int]] = []
        remaining_paths: List[Tuple[str,int]] = []
        estimated_total = 0

        for path, orig_size in image_sizes:
            estimated_size = int(orig_size * compression_factor)
            if estimated_total + estimated_size > max_bytes:
                remaining_paths.append((path, estimated_size))
                continue

            chosen_paths.append((path, estimated_size))
            estimated_total += estimated_size
            status = f"Selected(est): {len(chosen_paths)}/{total_images} images | Estimated size: {estimated_total/1024/1024:.1f}MB/{max_dir_size_gb*1024:.1f}MB"
            print(status + " " * 20, end="\r")

            if estimated_total >= max_bytes:
                break

        # Add any unprocessed paths to remaining_paths
        for path, orig_size in image_sizes:
            if not any(p == path for p, _ in chosen_paths) and not any(p == path for p, _ in remaining_paths):
                remaining_paths.append((path, int(orig_size * compression_factor)))

        # Print the final selection line as a persistent line, then return.
        final_status = f"Selected(est): {len(chosen_paths)}/{total_images} images | Estimated size: {estimated_total/1024/1024:.1f}MB/{max_dir_size_gb*1024:.1f}MB"
        print(final_status)
        return chosen_paths, remaining_paths

    def process_images(self, max_dir_size_gb: float, quality: float = 16.0) -> None:
        """
        Select a random subset of images (across nested folders) whose compressed
        total size does not exceed `max_dir_size_gb`, then write them into
        `self.compressed_dir` with filenames prefixed by a sequential count and
        folder name: "count_foldername_filename".

        - max_dir_size_gb: maximum size of final output directory in GB
        - quality: JPEG quality (1-100). Lower => smaller files.
        """
        # First, choose paths (estimated) from full set
        chosen_paths, remaining_paths = self.choose_random_subset_by_size(max_dir_size_gb, quality)

        if not chosen_paths:
            print("No images were selected (no images found or none fit the size limit).")
            return

        max_bytes = int(max_dir_size_gb * 1024 ** 3)

        # Compress selected paths (actual compression), but do not write yet.
        chosen_actual: List[Tuple[str, bytes]] = []
        actual_total = 0
        processed = 0

        # chosen_paths is list of (path, estimated_size)
        for path, est_size in chosen_paths:
            # If we've already reached the max budget, stop compressing further
            if actual_total >= max_bytes:
                break

            # If the estimated size doesn't fit the remaining budget, skip
            if actual_total + est_size > max_bytes:
                continue

            processed += 1
            try:
                data = self.compress_image_to_bytes(path, quality)
                size = len(data)
                # If this file doesn't fit in the remaining budget after actual compress, skip
                if actual_total + size > max_bytes:
                    continue
                chosen_actual.append((path, data))
                actual_total += size
                status = f"Compressing selected: {processed}/{len(chosen_paths)} | Actual size: {actual_total/1024/1024:.1f}MB/{max_dir_size_gb*1024:.1f}MB"
                print(status + " " * 20, end="\r")
                # If we've hit the budget exactly, stop early
                if actual_total >= max_bytes:
                    break
            except Exception:
                # skip failing files
                continue

        # If there's remaining budget, try to add more from remaining_paths (random order)
        if actual_total < max_bytes and remaining_paths:
            random.shuffle(remaining_paths)
            # remaining_paths is list of (path, estimated_size)
            for path, est_size in remaining_paths:
                if actual_total >= max_bytes:
                    break
                # Skip if estimated size doesn't fit
                if actual_total + est_size > max_bytes:
                    continue
                try:
                    data = self.compress_image_to_bytes(path, quality)
                    size = len(data)
                    if actual_total + size > max_bytes:
                        continue
                    chosen_actual.append((path, data))
                    actual_total += size
                    status = f"Adding extra: Actual size: {actual_total/1024/1024:.1f}MB/{max_dir_size_gb*1024:.1f}MB"
                    print(status + " " * 20, end="\r")
                    if actual_total >= max_bytes:
                        break
                except Exception:
                    continue

        print(" " * 100, end="\r")

        # Sort final chosen list by folder order
        def rel_folder_key(item: Tuple[str, bytes]) -> Tuple[str, str]:
            path = item[0]
            folder_rel = os.path.relpath(os.path.dirname(path), self.source_dir)
            folder_rel = '' if folder_rel == '.' else folder_rel
            return (folder_rel.lower(), os.path.basename(path).lower())

        chosen_sorted = sorted(chosen_actual, key=rel_folder_key)

        pad = len(str(len(chosen_sorted)))
        count = 1
        total_to_write = len(chosen_sorted)

        for orig_path, data in chosen_sorted:
            folder_rel = os.path.relpath(os.path.dirname(orig_path), self.source_dir)
            folder_rel = '' if folder_rel == '.' else folder_rel
            folder_name = folder_rel.replace(os.sep, '_') if folder_rel else 'root'
            base = os.path.basename(orig_path)
            out_name = f"{count:0{pad}d}_{folder_name}_{base}"
            out_path = os.path.join(self.compressed_dir, out_name)

            if os.path.exists(out_path):
                base_name, ext = os.path.splitext(out_name)
                suffix = 1
                while os.path.exists(os.path.join(self.compressed_dir, f"{base_name}_{suffix}{ext}")):
                    suffix += 1
                out_path = os.path.join(self.compressed_dir, f"{base_name}_{suffix}{ext}")

            try:
                with open(out_path, 'wb') as f:
                    f.write(data)
            except Exception as e:
                print(f"Failed to write {out_path}: {e}")
                continue

            status = f"Writing: {count}/{total_to_write} files to {self.compressed_dir}"
            print(status + " " * 20, end="\r")
            count += 1

        print(" " * 100, end="\r")
        print(f"Finished: wrote {count-1} files into '{self.compressed_dir}'")
