import os

from jibrish_to_hebrew import jibrish_to_hebrew
import eyed3


class FileManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir

    def perform_action(self, action):
        if action == 1:
            self.delete_empty_folders()
        elif action == 2:
            self.fix_jibrish_files()


    def build_folder_structure(self, func):
        """יצירת רשימת קבצים ותיקיות"""
        pass
    

    def delete_empty_folders(self):
    
        '''מחיקת תיקיות ריקות'''
        
        delete_folders = []

        # בניית רשימת התיקיות למחיקה
        for folder_name, subfolders, filenames in os.walk(self.root_dir, topdown=False):
            for subfolder in subfolders:
                folder_path = os.path.join(folder_name, subfolder)
                if not os.listdir(folder_path):
                    os.rmdir(folder_path)
                    delete_folders.append(folder_path)

        print(f'Num. of empty folders deleted: {len(delete_folders)}')




    def fix_jibrish_files(self):
    
        '''המרת קבצים עם קידוד פגום לעברית תקינה'''
        
        for root, dirs, files in os.walk(self.root_dir):
            for file in files:
                if file.lower().endswith((".mp3", ".wav", ".wma")):
                    file_path = os.path.join(root, file)

                    try:
                        # Load the MP3 file
                        audiofile = eyed3.load(file_path)

                        # Apply custom function to album name and title
                        if audiofile.tag.album:
                            new_album_name = jibrish_to_hebrew(audiofile.tag.album)
                            audiofile.tag.album = new_album_name

                        if audiofile.tag.title:
                            new_title = jibrish_to_hebrew(audiofile.tag.title)
                            audiofile.tag.title = new_title

                        # Save changes to the MP3 file
                        audiofile.tag.save()

                        print(f"Updated Album: {new_album_name}")
                        print(f"Updated Title: {new_title}")

                    except Exception as e:
                        print(f"Error processing {file}: {e}")




if __name__ == "__main__":
    root_directory = input('Add path folder\n>>>')
    file_manager = FileManager(root_directory)

    action = input('Choose action ([1] delete_empty_folders, [2] etc.)\n>>>')
    file_manager.perform_action(int(action))
