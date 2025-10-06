import os


class ExportDestinationManager:
    """
    Simple persistence manager for the export destination directory.
    Stores the path in a small text file alongside the application code.
    """

    def __init__(self, config_filename: str = "export_destination.txt"):
        # Place the config next to this file for simplicity
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(base_dir, config_filename)
        self.current_destination: str = ""

    def load_destination_on_startup(self):
        """Load a previously saved destination path if valid. Returns (path, is_valid)."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved_path = f.read().strip()

                if saved_path and os.path.isdir(saved_path):
                    self.current_destination = saved_path
                    return saved_path, True
                else:
                    # Clear invalid
                    self.clear_invalid_destination()
                    return "", False
            else:
                return "", False
        except Exception:
            return "", False

    def save_destination(self, path: str) -> bool:
        """Save a valid directory path to the config file."""
        try:
            if not path or not os.path.isdir(path):
                return False
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write(path)
            self.current_destination = path
            return True
        except Exception:
            return False

    def clear_invalid_destination(self):
        try:
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
        except Exception:
            pass
        self.current_destination = ""


