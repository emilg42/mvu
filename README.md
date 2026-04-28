# mvu

Simple utility for cutting and exporting event-based streams, inspired by OpenEB’s Metavision Studio.

## Usage

Add this function to your shell config, e.g. `~/.zshrc` or `~/.bashrc`:

```bash
mvu() {
  local mvu_dir="$HOME/Tools/mvu"
  "$mvu_dir/venv/bin/python" "$mvu_dir/cut.py" "$@"
}
