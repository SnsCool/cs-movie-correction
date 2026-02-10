"""Video silence trimming module using ffmpeg.

Trims silent portions from the beginning and end of Zoom recordings:
- Beginning: Waiting for student to join, no one talking
- End: Forgot to stop recording, silence at the end

Requires ffmpeg and ffprobe to be installed and available on PATH.
"""

import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)


def _get_duration(input_path: str) -> float:
    """Get the duration of a media file in seconds using ffprobe.

    Args:
        input_path: Path to the input media file.

    Returns:
        Duration in seconds.

    Raises:
        subprocess.CalledProcessError: If ffprobe fails.
        ValueError: If ffprobe output cannot be parsed.
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            input_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def detect_silence(
    input_path: str,
    silence_threshold: float = -40,
    min_duration: float = 10.0,
) -> list[tuple[float, float]]:
    """Detect silent regions in a media file using ffmpeg silencedetect.

    Runs ffmpeg's silencedetect audio filter and parses the stderr output
    for silence_start / silence_end markers.

    Args:
        input_path:        Path to the input media file.
        silence_threshold: Volume threshold in dB below which audio is
                           considered silent. Default -40 dB.
        min_duration:      Minimum silence duration in seconds to be
                           reported. Default 10.0 seconds.

    Returns:
        A list of ``(start, end)`` tuples representing each silent region
        in seconds.  If no silence is detected the list is empty.

    Raises:
        FileNotFoundError: If the input file does not exist.
        subprocess.CalledProcessError: If ffmpeg fails.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    logger.info(
        "Detecting silence in %s (threshold=%sdB, min_duration=%ss)",
        input_path,
        silence_threshold,
        min_duration,
    )

    result = subprocess.run(
        [
            "ffmpeg",
            "-i", input_path,
            "-af", f"silencedetect=noise={silence_threshold}dB:d={min_duration}",
            "-f", "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )

    stderr = result.stderr

    # Parse silence_start and silence_end pairs from ffmpeg stderr.
    # Lines look like:
    #   [silencedetect @ ...] silence_start: 0
    #   [silencedetect @ ...] silence_end: 15.5 | silence_duration: 15.5
    starts = re.findall(r"silence_start:\s*([\d.]+)", stderr)
    ends = re.findall(r"silence_end:\s*([\d.]+)", stderr)

    # If ffmpeg reported a silence_start without a matching silence_end it
    # means the silence extends to the very end of the file.
    if len(starts) > len(ends):
        total_duration = _get_duration(input_path)
        ends.append(str(total_duration))

    regions = [
        (float(s), float(e)) for s, e in zip(starts, ends)
    ]

    logger.info("Found %d silent region(s)", len(regions))
    for i, (s, e) in enumerate(regions):
        logger.debug("  Region %d: %.2fs - %.2fs (%.2fs)", i, s, e, e - s)

    return regions


def find_trim_points(
    input_path: str,
    silence_threshold: float = -40,
    min_duration: float = 10.0,
) -> tuple[float, float]:
    """Determine where to trim the beginning and end of a recording.

    Analyzes silent regions to find:
    - ``trim_start``: The end of the first silence region, if it begins
      at (or very near) 0 seconds. Otherwise 0.
    - ``trim_end``: The start of the last silence region, if it extends
      to (or very near) the end of the file. Otherwise the full duration.

    Args:
        input_path:        Path to the input media file.
        silence_threshold: Volume threshold in dB (passed to
                           :func:`detect_silence`).
        min_duration:      Minimum silence duration in seconds (passed to
                           :func:`detect_silence`).

    Returns:
        A ``(trim_start, trim_end)`` tuple in seconds.

    Raises:
        FileNotFoundError: If the input file does not exist.
    """
    regions = detect_silence(input_path, silence_threshold, min_duration)
    total_duration = _get_duration(input_path)

    trim_start = 0.0
    trim_end = total_duration

    if not regions:
        logger.info("No silence detected; no trimming needed")
        return (trim_start, trim_end)

    # Check if the first silence region starts at (or very near) the beginning.
    first_start, first_end = regions[0]
    if first_start < 1.0:
        trim_start = first_end
        logger.info(
            "Leading silence detected: trimming first %.2fs", trim_start
        )

    # Check if the last silence region extends to (or very near) the end.
    last_start, last_end = regions[-1]
    if total_duration - last_end < 1.0:
        trim_end = last_start
        logger.info(
            "Trailing silence detected: trimming after %.2fs", trim_end
        )

    # Handle the case where the entire video is silent.
    if trim_start >= trim_end:
        logger.warning(
            "Entire file appears to be silent (trim_start=%.2f >= trim_end=%.2f)",
            trim_start,
            trim_end,
        )
        return (0.0, total_duration)

    return (trim_start, trim_end)


def trim_video(
    input_path: str,
    output_path: str,
    start: float = 0,
    end: float = 0,
) -> str:
    """Trim a video file using ffmpeg with codec copy (no re-encoding).

    Args:
        input_path:  Path to the input video file.
        output_path: Path for the trimmed output file.
        start:       Start time in seconds. Default 0.
        end:         End time in seconds. If 0, uses the full duration.

    Returns:
        The ``output_path`` string.

    Raises:
        FileNotFoundError: If the input file does not exist.
        subprocess.CalledProcessError: If ffmpeg fails.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if end <= 0:
        end = _get_duration(input_path)

    logger.info(
        "Trimming %s -> %s (%.2fs to %.2fs)",
        input_path,
        output_path,
        start,
        end,
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    subprocess.run(
        [
            "ffmpeg",
            "-i", input_path,
            "-ss", str(start),
            "-to", str(end),
            "-c", "copy",
            "-y",
            output_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    logger.info("Trimmed video saved to %s", output_path)
    return output_path


def auto_trim(input_path: str, output_path: str = "") -> str:
    """Automatically trim leading and trailing silence from a recording.

    This is the main entry point.  It detects silence, determines trim
    points, and produces a trimmed copy of the video.

    If no silence is detected at the beginning or end, the original file
    path is returned without creating a new file.

    Args:
        input_path:  Path to the input video file.
        output_path: Path for the trimmed output file.  If empty, a path
                     is generated by inserting ``_trimmed`` before the
                     file extension.

    Returns:
        The path to the trimmed file, or ``input_path`` if no trimming
        was needed.

    Raises:
        FileNotFoundError: If the input file does not exist.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    logger.info("Auto-trimming %s", input_path)

    trim_start, trim_end = find_trim_points(input_path)
    total_duration = _get_duration(input_path)

    # No trimming needed if the points span the full file.
    if trim_start < 1.0 and total_duration - trim_end < 1.0:
        logger.info("No significant silence at start/end; skipping trim")
        return input_path

    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_trimmed{ext}"

    return trim_video(input_path, output_path, start=trim_start, end=trim_end)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <input_video> [output_video]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else ""

    result = auto_trim(input_file, output_file)
    print(f"Result: {result}")
