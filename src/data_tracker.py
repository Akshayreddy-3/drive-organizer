import json
import os
from datetime import datetime

class DataTracker:
    """
    DataTracker handles persisting upload history, folder structures,
    file details, and verification status to a local JSON file
    (tracker_data.json) for the web dashboard.
    """
    
    def __init__(self, storage_path="tracker_data.json"):
        self.storage_path = storage_path
        self.data = self._load_data()

    def _load_data(self):
        """Loads data from the JSON file or returns an empty structure."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                # Ensure new fields exist (backwards-compatible)
                if "folder_tree" not in data:
                    data["folder_tree"] = {}
                if "verified_files" not in data:
                    data["verified_files"] = {}
                if "all_files" not in data:
                    data["all_files"] = []
                return data
            except (json.JSONDecodeError, IOError):
                pass
        
        return {
            "total_files": 0,
            "total_groups": 0,
            "last_upload": None,
            "groups": {},
            "history": [],
            "folder_tree": {},
            "verified_files": {},
            "all_files": []
        }

    def _save_data(self):
        """Saves current data to the JSON file."""
        with open(self.storage_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def log_run(self, groups, is_preview=False, upload_results=None, folder_paths=None):
        """
        Logs a sync run.
        
        Args:
            groups (dict): Dict of {group_name: [list_of_files]}
            is_preview (bool): Whether this was a preview run.
            upload_results (dict): Optional dict of {group_name: [result_dicts]}
                Each result dict has: status, local_path, file (with name)
            folder_paths (dict): Optional dict of {group_name: "project/month/date"}
        """
        run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        
        file_count = sum(len(files) for files in groups.values())
        group_count = len(groups)
        
        # Update aggregates
        if not is_preview:
            self.data["total_files"] += file_count
            self.data["last_upload"] = run_date
            
            # Update folder stats and file tracking
            for name, files in groups.items():
                if name not in self.data["groups"]:
                    self.data["groups"][name] = {"count": 0, "files": []}
                
                self.data["groups"][name]["count"] += len(files)
                
                # Get the Drive path for this group
                drive_path = ""
                if folder_paths and name in folder_paths:
                    drive_path = folder_paths[name]
                
                # Build file entries with richer metadata
                for f in files:
                    file_basename = os.path.basename(f) if os.path.sep in f else f
                    
                    # Determine status from upload_results
                    status = "uploaded"
                    if upload_results and name in upload_results:
                        for r in upload_results[name]:
                            r_name = os.path.basename(r.get('local_path', ''))
                            if r_name == file_basename:
                                status = r.get('status', 'uploaded')
                                break
                    
                    file_entry = {
                        "name": file_basename,
                        "date": run_date,
                        "path": drive_path,
                        "status": status,
                        "run_id": run_id
                    }
                    
                    # Add to group files
                    self.data["groups"][name]["files"].append(file_entry)
                    
                    # Add to global all_files list
                    file_entry_global = dict(file_entry)
                    file_entry_global["group"] = name
                    self.data["all_files"].append(file_entry_global)
                
                # Keep a window of recent files per group
                self.data["groups"][name]["files"] = self.data["groups"][name]["files"][-50:]
            
            # Keep global file list to last 500
            self.data["all_files"] = self.data["all_files"][-500:]
            
            # Update folder tree
            if folder_paths:
                for group_name, path_str in folder_paths.items():
                    parts = path_str.split("/") if path_str else []
                    if len(parts) >= 1:
                        project = parts[0]
                        if project not in self.data["folder_tree"]:
                            self.data["folder_tree"][project] = {}
                        if len(parts) >= 2:
                            month = parts[1]
                            if month not in self.data["folder_tree"][project]:
                                self.data["folder_tree"][project][month] = []
                            if len(parts) >= 3:
                                date = parts[2]
                                if date not in self.data["folder_tree"][project][month]:
                                    self.data["folder_tree"][project][month].append(date)

        # Add to history
        self.data["history"].append({
            "id": run_id,
            "date": run_date,
            "files": file_count,
            "groups": group_count,
            "is_preview": is_preview
        })
        # Keep last 100 runs
        self.data["history"] = self.data["history"][-100:]
        
        # Update total groups count
        self.data["total_groups"] = len(self.data["groups"])
        
        self._save_data()

    def mark_verified(self, file_key):
        """Mark a file as verified (user confirmed it's in Drive)."""
        self.data["verified_files"][file_key] = True
        self._save_data()

    def unmark_verified(self, file_key):
        """Remove verification mark from a file."""
        if file_key in self.data["verified_files"]:
            del self.data["verified_files"][file_key]
            self._save_data()

    def get_summary(self):
        """Returns a summary of the tracked data."""
        return {
            "total_files": self.data["total_files"],
            "total_groups": self.data["total_groups"],
            "last_upload": self.data["last_upload"]
        }
