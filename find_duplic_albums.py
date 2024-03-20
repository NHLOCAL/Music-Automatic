import os
from collections import defaultdict
from difflib import SequenceMatcher
from mutagen.easyid3 import EasyID3
import re

class FolderComparer:
    def __init__(self, folder_paths):
        self.folder_paths = folder_paths
        self.folder_files = defaultdict(list)

    def build_folder_structure(self, root_dir):
        """
        Generate a list of files and their corresponding folder paths.
        """
        for root, dirs, _ in os.walk(root_dir):
            for _dir in dirs:
                dir_path = os.path.join(root, _dir)
                files_in_dir = [i for i in os.listdir(dir_path) if i.lower().endswith((".mp3", ".flac"))]

                if files_in_dir == []:
                    continue

                if len(set([re.sub(r'\d', '', i) for i in files_in_dir])) == 1:
                    continue

                if any(True for i in files_in_dir if "רצועה" in i or "track" in i.lower() or "audiotrack" in i.lower()):
                    continue

                yield dir_path, files_in_dir

    def gather_file_info(self, folder_path, files_in_dir):
        """
        Collect information about files within a folder.
        """
        file_info = defaultdict(list)
        for file in files_in_dir:
            file_path = os.path.join(folder_path, file)
            try:
                audio = EasyID3(file_path)
                artist = audio['artist'][0] if 'artist' in audio else None
                album = audio['album'][0] if 'album' in audio else None
                title = audio['title'][0] if 'title' in audio else None
                file_info[folder_path].append({
                    'file': file,
                    'artist': artist,
                    'album': album,
                    'title': title,
                })
            except Exception as e:
                print(f"Error processing {file}: {e}")

        return file_info

    def get_file_lists(self):
        """
        Return the lists of files and their information.
        """
        for folder_path in self.folder_paths:
            for dir_path, files_in_dir in self.build_folder_structure(folder_path):
                self.folder_files.update(self.gather_file_info(dir_path, files_in_dir))

        return self.folder_files

    def find_similar_folders(self, folder_files):
        """
        Find similar folders based on the information of file lists.
        """
        similar_folders = defaultdict(list)
        processed_pairs = set()
        for folder_path, files in folder_files.items():
            for other_folder_path, other_files in folder_files.items():
                if folder_path != other_folder_path and (other_folder_path, folder_path) not in processed_pairs:
                    similarity_scores = []
                    for file_info in files:
                        for other_file_info in other_files:
                            file_similarity = 0
                            if file_info['album'] and other_file_info['album']:
                                file_similarity += self.similar(file_info['album'], other_file_info['album'])
                            if file_info['artist'] and other_file_info['artist']:
                                file_similarity += self.similar(file_info['artist'], other_file_info['artist'])
                            if file_info['file'] == other_file_info['file']:
                                file_similarity += 1
                            similarity_scores.append(file_similarity)
                    if similarity_scores:
                        avg_similarity = sum(similarity_scores) / len(similarity_scores)
                        if avg_similarity > 2:  # Adjust threshold as needed
                            similar_folders[folder_path].append(other_folder_path)
                            processed_pairs.add((folder_path, other_folder_path))

        return similar_folders
    

    def similar(self, a, b):
        """
        Calculate similarity ratio between two strings.
        """
        return SequenceMatcher(None, a, b).ratio()

    def main(self):
        """
        Main function to execute file comparison and find similar folders.
        """
        folder_files = self.get_file_lists()
        similar_folders = self.find_similar_folders(folder_files)
        for folder_path, similar_paths in similar_folders.items():
            print(f"Folder: {folder_path}")
            print("Similar folders:")
            for similar_path in similar_paths:
                print(f"- {similar_path}")

if __name__ == "__main__":
    folder_paths = ["path/to/folder1", "path/to/folder2"]
    comparer = FolderComparer(folder_paths)
    comparer.main()
