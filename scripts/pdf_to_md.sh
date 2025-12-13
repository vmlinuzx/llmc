#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: pdf_to_md.sh [options] <input.pdf>

Options:
  -o, --output FILE       Path for the generated Markdown (default: same directory, .md extension)
  -m, --media-dir DIR     Directory for extracted media (default: <output>_assets)
      --no-media          Skip media extraction
  -h, --help              Show this message

Example:
  scripts/pdf_to_md.sh DOCS/RESEARCH/example.pdf
  scripts/pdf_to_md.sh -o DOCS/RESEARCH/example.md --media-dir DOCS/RESEARCH/example_assets example.pdf

Requires pandoc ≥ 2.0 and pdftohtml (Poppler).
USAGE
}

die() {
  echo "pdf_to_md.sh: $*" >&2
  exit 1
}

ensure_pandoc() {
  if ! command -v pandoc >/dev/null 2>&1; then
    die "pandoc is not installed or not in PATH"
  fi
  if ! command -v pdftohtml >/dev/null 2>&1; then
    die "pdftohtml is not installed or not in PATH (usually provided by poppler-utils)"
  fi
}

input_file=""
output_file=""
media_dir=""
extract_media=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -o|--output)
      [[ $# -lt 2 ]] && die "--output requires a value"
      output_file="$2"
      shift 2
      ;;
    -m|--media-dir)
      [[ $# -lt 2 ]] && die "--media-dir requires a value"
      media_dir="$2"
      shift 2
      ;;
    --no-media)
      extract_media=0
      shift
      ;;
    --)
      shift
      break
      ;;
    -* )
      die "unknown option: $1"
      ;;
    * )
      if [[ -n "$input_file" ]]; then
        die "multiple input files provided; only one is supported"
      fi
      input_file="$1"
      shift
      ;;
  esac
done

# Handle any trailing args after --
if [[ -z "$input_file" && $# -gt 0 ]]; then
  input_file="$1"
  shift
fi

[[ -n "$input_file" ]] || die "no input PDF provided"

if [[ ! -f "$input_file" ]]; then
  die "input file not found: $input_file"
fi

ensure_pandoc

input_abs=$(realpath "$input_file")
input_dir=$(dirname "$input_abs")
input_base=$(basename "$input_abs")
stem="${input_base%.*}"

if [[ -z "$output_file" ]]; then
  output_file="$input_dir/${stem}.md"
fi

if [[ $extract_media -eq 1 ]]; then
  if [[ -z "$media_dir" ]]; then
    media_dir="${output_file%.*}_assets"
  fi
  media_arg=("--extract-media=$media_dir")
else
  media_arg=()
fi

mkdir -p "$(dirname "$output_file")"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

html_base="$tmp_dir/converted"

# Generate a single HTML file from the PDF; suppress stdout spam.
pdftohtml -s -i -noframes "$input_abs" "$html_base" >/dev/null 2>&1

html_file="${html_base}.html"
[[ -f "$html_file" ]] || die "failed to generate intermediate HTML via pdftohtml"

pandoc "$html_file" -f html -t gfm "${media_arg[@]}" -o "$output_file"

echo "Generated $output_file"
if [[ $extract_media -eq 1 ]]; then
  echo "Media extracted to $media_dir"
fi
