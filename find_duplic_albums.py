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

                if len(files_in_dir) <= 2:
                    continue

                yield dir_path, files_in_dir

    def gather_file_info(self, folder_path, files_in_dir):
        """
        Collect information about files within a folder.
        """
        file_info = defaultdict(list)

        # Extract titles from the files
        titles = []
        for file in files_in_dir:
            file_path = os.path.join(folder_path, file)
            try:
                audio = EasyID3(file_path)
                title = audio['title'][0] if 'title' in audio else None
                if title:
                    titles.append(title)
            except Exception as e:
                print(f"Error processing {file}: {e}")

        # Check generic names for the titles
        generic_titles = self.check_generic_names(titles) if titles else None
        generic_names = self.check_generic_names(files_in_dir)

        for file in files_in_dir:
            file_path = os.path.join(folder_path, file)
            try:
                audio = EasyID3(file_path)
                artist = audio['artist'][0] if 'artist' in audio else None
                album = audio['album'][0] if 'album' in audio else None
                title = audio['title'][0] if 'title' in audio else None

                # Determine 'file' value based on generic names
                file_value = None if generic_names else file

                # Determine 'title' value based on generic names
                title_value = None if generic_titles else title

                file_info[folder_path].append({
                    'file': file_value,
                    'artist': artist,
                    'album': album,
                    'title': title_value,
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
                    
                    for parameter in ['file', 'title', 'album', 'artist']:
                        total_similarity = 0
                        for file_info, other_file_info in zip(files, other_files):
                            if file_info[parameter] and other_file_info[parameter]:
                                similarity_score = self.similar(file_info[parameter], other_file_info[parameter])
                                total_similarity += similarity_score
                        folder_similarity[parameter] = total_similarity / total_files

                    # Apply weights to individual scores
                    weighted_score = sum(folder_similarity[param] * weights[param] for param in folder_similarity)
                    folder_similarity['weighted_score'] = weighted_score

                    if folder_similarity:
                        similar_folders[(folder_path, other_folder_path)] = folder_similarity
                        processed_pairs.add((folder_path, other_folder_path))

        return similar_folders


    # בדיקה אם רשימת קבצים בתיקיה הם בעלי שמות דומים מידי
    def check_generic_names(self, files_list):
        n = len(files_list)
        total_similarity = 0.0
        total_pairs = 0
        files_list_cleaned = [file.split('.')[0] for file in files_list]
        files_list_cleaned = [re.sub(r'\d', '', i) for i in files_list_cleaned]
        
        for i in range(n):
            for j in range(i+1, n):
                similarity_score = SequenceMatcher(None, files_list_cleaned[i], files_list_cleaned[j]).ratio()
                total_similarity += similarity_score
                total_pairs += 1
        
        if total_pairs == 0:
            return False
        
        average_similarity = total_similarity / total_pairs
        return average_similarity >= 0.7



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
    folder_paths = [r"C:\Users\משתמש\Documents\space_automatic"]
    comparer = FolderComparer(folder_paths)
    comparer.main()
