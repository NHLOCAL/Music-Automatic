import os
from collections import defaultdict
from difflib import SequenceMatcher
from mutagen.easyid3 import EasyID3
from mutagen import File
import re
from main import MusicManger

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
        weights = {'file': 4.5, 'album': 1.0, 'title': 3.0, 'artist': 0.5, 'folder_name': 1.0}

        similar_folders = defaultdict(dict)
        processed_pairs = set()
        for folder_path, files in folder_files.items():
            for other_folder_path, other_files in folder_files.items():
                if folder_path != other_folder_path and (other_folder_path, folder_path) not in processed_pairs and len(files) == len(other_files):
                    folder_similarity = {}
                    total_files = len(files)
                    
                    # Calculate folder name similarity
                    folder_name_similarity = self.similar(os.path.basename(folder_path), os.path.basename(other_folder_path))
                    folder_similarity['folder_name'] = folder_name_similarity

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
        If similarity level is less than 0.7, the result will be 0.
        """
        _ratio = SequenceMatcher(None, a, b).ratio()
        if _ratio < 0.75:
            return 0.0
        return _ratio



    def main(self):
        """
        Main function to execute file comparison and find similar folders.
        """
        self.folder_files = self.get_file_lists()
        self.similar_folders = self.find_similar_folders(self.folder_files)
        
        # Sort similar folders by weighted score in descending order
        self.sorted_similar_folders = sorted(self.similar_folders.items(), key=lambda x: x[1]['weighted_score'], reverse=True)
        
        for folder_pair, similarities in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            print(f"Folder: {folder_path}")
            print(f"Similar folder: {other_folder_path}")
            print("Similarity scores:")
            for parameter, score in similarities.items():
                print(f"- {parameter.capitalize()}: {score}")
            print()



import shutil

class SelectAndThrow:
    def __init__(self, sorted_similar_folders):
        self.sorted_similar_folders = sorted_similar_folders

    def select_better_folder(self):
        """
        Select the better folder between duplicate folders.
        """
        for folder_pair, similarities in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            
            # Check if the other folder is still available (not deleted in previous iterations)
            if os.path.exists(other_folder_path):
                print(f"Folder: {folder_path}")
                print(f"Similar folder: {other_folder_path}")
                
                # Ask user to select the better folder
                choice = input("Which folder do you want to keep? (Enter '1' for first folder, '2' for second folder): ")
                
                # If user chooses the second folder, ask for deletion confirmation
                if choice == '2':
                    confirm_delete = input("Do you want to delete the second folder? (y/n): ")
                    if confirm_delete.lower() == 'y':
                        self.delete_folder(other_folder_path)
                print()

    def delete_folder(self, folder_path):
        """
        Delete the specified folder.
        """
        shutil.rmtree(folder_path)
        print(f"Deleted folder: {folder_path}")

    def quality_sort(self):
        """
        Compare folders based on certain quality criteria.
        """
        for folder_pair, similarities in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            folder_quality = self.compare_quality(folder_path, other_folder_path)
            print(f"Folder: {folder_path}")
            print(f"Similar folder: {other_folder_path}")
            print(f"Quality of {folder_path}: {folder_quality}")
            print(f"Quality of {other_folder_path}: {1 - folder_quality}")
            print()

    def compare_quality(self, folder_path1, folder_path2):
        """
        Compare the quality of two folders.
        """

        files_list1 = [i for i in os.listdir(folder_path1) if i.lower().endswith((".mp3", ".flac"))]

        files_list2 = [i for i in os.listdir(folder_path2) if i.lower().endswith((".mp3", ".flac"))]

        # Check if the songs contain an album art
        # You can implement this logic using any method you prefer. For demonstration, let's assume it's always present.
        album_art_present1 = self.check_albumart(folder_path1)
        album_art_present2 = self.check_albumart(folder_path2)

        # Check if the file names are too identical
        # You can use the check_generic_names function from the FolderComparer class for this
        folder_comparer = FolderComparer([r'C:\Users\משתמש\Documents\space_automatic'])
        folder1_generic_names = folder_comparer.check_generic_names(files_list1)
        folder2_generic_names = folder_comparer.check_generic_names(files_list2)

        grade_generic1 = 0 if folder1_generic_names else 1
        grade_generic2 = 0 if folder2_generic_names else 1
        

        # Calculate quality based on the tests
        quality1 = 1 - album_art_present1 + grade_generic1
        quality2 = 1 - album_art_present2 + grade_generic2

        # Returning the quality of the first folder (can be adjusted based on comparison logic)
        return quality1, quality2

    def check_albumart(self, folder_path):
        '''בדיקה אם שירים מכילים תמונת אלבום'''
        files_procces = set()
        files_list = [i for i in os.listdir(folder_path) if i.lower().endswith((".mp3", ".flac"))]
        
        for file in files_list:
            result = False
            file_path = os.path.join(folder_path, file)
            meta_file = File(file_path)
            
            try:
                for k in meta_file.keys():
                    if not u'covr' in k and not u'APIC' in k:
                        result = False
                    else:
                        result = True
                        break
            
            except: pass
            
            if result is False:
                files_procces.add(file_path)
        
        return len(files_procces) / len(files_list)




if __name__ == "__main__":
    folder_paths = [r"C:\Users\משתמש\Documents\space_automatic"]
    comparer = FolderComparer(folder_paths)
    comparer.main()
