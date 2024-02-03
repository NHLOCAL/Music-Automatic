import os

class FileManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir

    def delete_empty_folders(self):
        delete_folders = []

        for folder_name, subfolders, filenames in os.walk(self.root_dir, topdown=False):
            for subfolder in subfolders:
                folder_path = os.path.join(folder_name, subfolder)
                if not os.listdir(folder_path):
                    os.rmdir(folder_path)
                    delete_folders.append(folder_path)

        print(f'Num. of empty folders deleted: {len(delete_folders)}')

    def perform_action(self, action):
        if action == "delete_empty_folders":
            self.delete_empty_folders()
        # Add more actions as needed

if __name__ == "__main__":
    root_directory = input('Add path folder\n>>>')
    file_manager = FileManager(root_directory)

    action = input('Choose action (delete_empty_folders, etc.)\n>>>')
    file_manager.perform_action(action)
