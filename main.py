import os




class FileManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir



    def build_folder_structure(self, func):
        """יצירת רשימת קבצים ותיקיות"""
        pass
    

    def delete_empty_folders(self):
        delete_folders = []

        # בניית רשימת התיקיות למחיקה
        for folder_name, subfolders, filenames in os.walk(self.root_dir, topdown=False):
            for subfolder in subfolders:
                folder_path = os.path.join(folder_name, subfolder)
                if not os.listdir(folder_path):
                    os.rmdir(folder_path)
                    delete_folders.append(folder_path)

        print(f'Num. of empty folders deleted: {len(delete_folders)}')

    def perform_action(self, action):
        if action == 1:
            self.delete_empty_folders()
        # Add more actions as needed

if __name__ == "__main__":
    root_directory = input('Add path folder\n>>>')
    file_manager = FileManager(root_directory)

    action = input('Choose action ([1] delete_empty_folders, [2] etc.)\n>>>')
    file_manager.perform_action(int(action))
