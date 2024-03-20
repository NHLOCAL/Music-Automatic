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
        Return weighted score for all files in each folder for each parameter,
        normalized by the number of files in the folder.
        """
        # Define weights for each parameter
        weights = {'file': 5.0, 'album': 1.0, 'title': 3.5, 'artist': 0.5}

        similar_folders = defaultdict(dict)
        processed_pairs = set()
        for folder_path, files in folder_files.items():
            for other_folder_path, other_files in folder_files.items():
                if folder_path != other_folder_path and (other_folder_path, folder_path) not in processed_pairs and len(files) == len(other_files):
                    folder_similarity = {}
                    total_files = len(files)
                    
                    # Calculate similarity scores for each parameter
                    for parameter in ['file', 'album', 'artist', 'title']:
                        param_similarity = sum(self.similar(file_info[parameter], other_file_info[parameter]) if file_info[parameter] and other_file_info[parameter] else 0 for file_info, other_file_info in zip(files, other_files))
                        folder_similarity[parameter] = param_similarity / total_files

                    # Apply weights to individual scores
                    weighted_score = sum(folder_similarity[param] * weights[param] for param in folder_similarity)
                    folder_similarity['weighted_score'] = weighted_score

                    if folder_similarity:
                        similar_folders[(folder_path, other_folder_path)] = folder_similarity
                        processed_pairs.add((folder_path, other_folder_path))

        return similar_folders





    def similar(self, a, b):
        """
        Calculate similarity ratio between two strings.
        If similarity level is less than 0.5, the result will be 0.
        """
        _ratio = SequenceMatcher(None, a, b).ratio()
        if _ratio < 0.5:
            return 0.0
        return _ratio


    def main(self):
        """
        Main function to execute file comparison and find similar folders.
        """
        folder_files = self.get_file_lists()
        similar_folders = self.find_similar_folders(folder_files)
        
        # Sort similar folders by weighted score in descending order
        sorted_similar_folders = sorted(similar_folders.items(), key=lambda x: x[1]['weighted_score'], reverse=True)
        
        for folder_pair, similarities in sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            print(f"Folder: {folder_path}")
            print(f"Similar folder: {other_folder_path}")
            print("Similarity scores:")
            for parameter, score in similarities.items():
                print(f"- {parameter.capitalize()}: {score}")
            print()




if __name__ == "__main__":
    folder_paths = [r"D:\דברים שמתחדשים\חדשים כסליו\בעלזא"]
    comparer = FolderComparer(folder_paths)
    comparer.main()
