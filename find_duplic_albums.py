import os
from collections import defaultdict
from difflib import SequenceMatcher
from mutagen.easyid3 import EasyID3
from mutagen import File
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

class SelectAndThrow(FolderComparer):

    def quality_sort(self):
        """
        Compare folders based on certain quality criteria.
        """
        # Determine the maximum length of folder paths for formatting
        max_folder_path_length = 60
        
        print(f'{"Folder Name":<{max_folder_path_length}} {"Quality Score"}')
        print('-' * (max_folder_path_length + 20))
        
        for folder_pair, similarities in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            folder_quality1, folder_quality2 = self.compare_quality(folder_path, other_folder_path)
            
            if folder_quality1 > folder_quality2:
                print(colors.GREEN + f'{folder_path:<{max_folder_path_length}} {folder_quality1}' + colors.RESET)
                print(f'{other_folder_path:<{max_folder_path_length}} {folder_quality2}')
            elif folder_quality2 > folder_quality1:
                print(f'{folder_path:<{max_folder_path_length}} {folder_quality1}')
                print(colors.GREEN + f'{other_folder_path:<{max_folder_path_length}} {folder_quality2}' + colors.RESET)
            else:
                print(colors.CYAN + f'{folder_path:<{max_folder_path_length}} {folder_quality1}' + colors.RESET)
                print(colors.CYAN + f'{other_folder_path:<{max_folder_path_length}} {folder_quality2}' + colors.RESET)
            print()


    def compare_quality(self, folder_path1, folder_path2):
        """
        Compare the quality of two folders.
        """
        # Check if the songs contain an album art
        album_art_present1 = self.check_albumart(folder_path1)
        album_art_present2 = self.check_albumart(folder_path2)

        # Extract folder information for both paths
        quality_compar = self.extract_folder_info()

        folder_quality1 = quality_compar[folder_path1]
        folder_quality2 = quality_compar[folder_path2]

        # Comparing quality based on the difference in scores
        keys = ['empty_names_score', 'empty_titles_score', 'empty_artists_score', 'empty_albums_score']

        quality_difference = defaultdict(dict)
        for key in keys:
            quality_difference[key] = 2 if folder_quality1[key] > folder_quality2[key] else 1 if folder_quality1[key] < folder_quality2[key] else None

        quality_difference['albumart_score'] = 2 if album_art_present1 > album_art_present2 else 1 if album_art_present1 < album_art_present2 else None


        # Calculate quality based on the tests
        folder_quality1 = sum(1 for score in quality_difference.values() if score == 1)
        folder_quality2 = sum(1 for score in quality_difference.values() if score == 2)

        # Returning the quality of the first folder (can be adjusted based on comparison logic)
        return folder_quality1, folder_quality2
    

    def extract_folder_info(self):
        folder_structure = self.folder_files
        quality_compar = defaultdict(dict)
        
        for folder, files in folder_structure.items():
            total_files = len(files)
            quality_compar[folder]['empty_names'] = sum(1 for file_info in files if file_info['file'] is None)
            quality_compar[folder]['empty_titles'] = sum(1 for file_info in files if file_info['title'] is None)
            quality_compar[folder]['empty_artists'] = sum(1 for file_info in files if file_info['artist'] is None)
            quality_compar[folder]['empty_albums'] = sum(1 for file_info in files if file_info['album'] is None)
            quality_compar[folder]['total_files'] = total_files
            
            # Calculate scores
            for key in ['empty_names', 'empty_titles', 'empty_artists', 'empty_albums']:
                quality_compar[folder][f'{key}_score'] = quality_compar[folder][key] / total_files if total_files > 0 else 0
        
        return quality_compar
    

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
    comparer = SelectAndThrow(folder_paths)
    comparer.main()



# ANSI color codes
class colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'