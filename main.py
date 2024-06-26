import os
from jibrish_to_hebrew import fix_jibrish, check_jibrish
from mutagen import File
from mutagen.easyid3 import EasyID3

# הפעלה ראשונית ופעולות בסיס
class FileManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir

    def perform_action(self, action):
        if action == 1:
            self.delete_empty_folders()
        elif action == 2:
            self.fix_jibrish_files()
        elif action == 3:
            self.check_albumart()
        elif action == 4:
            self.fix_track_names()


    def build_folder_structure(self):
        """יצירת רשימת קבצים ותיקיות"""
        for root, dirs, files in os.walk(self.root_dir):
            for file in files:
                if file.lower().endswith((".mp3", ".wav", ".wma")):
                    file_path = os.path.join(root, file)
                    yield file_path


    def summary_message(self, files_list, description):
        """הדפסת הודעת סיכום בסיום הפעלת פונקציה"""
        
        self.counting = len(files_list)
        
        if self.counting < 1:
            return 'No matching files or folders found, no changes made!'
        
        else:    
            return (f'Num. of {description}: {self.counting}')

    def run_func(self, func_name):
        '''רצף פעולות קבוע שמפעיל פונקציה רצויה על מערכת הקבצים'''

        self.list_generator = self.build_folder_structure()
        self.files_procces = set()

        # Check if the function exists as an instance method
        if hasattr(self, func_name) and callable(getattr(self, func_name)):
            # Get the function object
            func = getattr(self, func_name)
            # Call the function
            return_func = func()
            message = self.summary_message(*return_func)
            print(message)
        else:
            print(f"Instance method '{func_name}' not found or is not callable.")




# פעולות על מוזיקה ותיקיות
class MusicManger(FileManager):

    def check_albumart(self):
        '''בדיקה אם שירים מכילים תמונת אלבום'''
        
        for file_path in self.list_generator:
            
            result = False
            meta_file = File(file_path)
            
            for k in meta_file.keys():
                if not u'covr' in k and not u'APIC' in k:
                    result = False
                else:
                    result = True
                    break
            
            if result is False:
                self.files_procces.add(file_path)
        
        return self.files_procces, 'Files without album art found'

    
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

        self.summary_message(delete_folders, 'empty folders deleted')


# תיקון ושינוי שמות קבצים במגוון שיטות
class FixNames(FileManager):
    
    def fix_track_names(self):
        '''Replace "track" with "רצועה" in file names and titles'''
        
        for file_path in self.list_generator:
            file_name = os.path.basename(file_path)
            file_name, file_extension = os.path.splitext(file_name)

            # Load the MP3 file
            audiofile = EasyID3(file_path)

            # Flag to track changes in the file
            changed = False

            # Check if "track" exists in the title
            if audiofile.get('title') and "track" in audiofile.get('title')[0].lower():
                # Replace "track" with "רצועה" in the title
                try:
                    new_title = audiofile.get('title')[0].lower().replace("track", "רצועה")
                    audiofile['title'] = new_title
                    print(f"Updated Title: {new_title}")
                    changed = True
                    audiofile.save()
                except:
                    pass
 
            # Check if "track" exists in the file name
            if "track" in file_name.lower():
                # Replace "track" with "רצועה" in the file name
                new_file_name = file_name.lower().replace("track", "רצועה") + file_extension
                new_file_path = os.path.join(os.path.dirname(file_path), new_file_name)
                os.rename(file_path, new_file_path)
                print(f"Updated File Name: {new_file_path}")
                changed = True

            # Save changes to the MP3 file if changes were made
            if changed:
                self.files_procces.add(file_path)

        return self.files_procces, 'Track names fixed'



    def fix_jibrish_files(self):
        '''המרת קבצים עם קידוד פגום לעברית תקינה'''
        
        for file_path in self.list_generator:
            # Load the MP3 file
            audiofile = EasyID3(file_path)
            
            # Flag to track changes in the file
            changed = False
            
            # Define the fields to check and update
            fields_to_check = ['album', 'title', 'artist', 'albumartist', 'genre']
            
            for field in fields_to_check:
                try:
                    if field in audiofile and check_jibrish(audiofile[field][0]):
                        new_value = fix_jibrish(audiofile[field][0])
                        audiofile[field] = new_value
                        print(f"Updated {field.capitalize()}: {new_value}")
                        changed = True
                except:
                    pass
                
            # Save changes to the MP3 file if changes were made
            if changed:
                audiofile.save()
                self.files_procces.add(file_path)
                        
        return self.files_procces, 'Damaged files repaired'




if __name__ == "__main__":
    while True:
        root_directory = input('Add path folder\n>>> ')
        
        # Check if the entered path exists
        if os.path.exists(root_directory):
            break
        else:
            print("The entered path does not exist. Please enter a valid path.")


    file_manager = FileManager(root_directory)

    while True: 
        action = input('''
Choose action:

    [1] delete_empty_folders = Deleting empty folders from the folder tree
    [2] fix_jibrish_files = Fix wrong encoding in the music files
    [3] check_albumart = Checking files that do not contain album art

>>>''')
    
        if action.isdigit():
            break
        else:
            print('Please enter a valid number to continue!')

    file_manager.perform_action(int(action))
