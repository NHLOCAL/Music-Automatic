import os



class FileManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        
        
    def build_folder_structure(self):
        """יצירת רשימת קבצים ותיקיות"""
        for root, dirs, files in os.walk(self.root_dir):
            for _dir in dirs:
                dir_path = os.path.join(root, _dir)
                files_in_dir =  [i for i in os.listdir(dir_path) if i.lower().endswith((".mp3", ".wav", ".wma"))]
                
                if files_in_dir == []:
                    continue
                
                if any(True for i in files_in_dir if "רצועה" in i or "track" in i.lower()):
                    continue
                    
                yield dir_path, files_in_dir,  _dir
                
    
    def summary_message(self, files_list, description):
        """הדפסת הודעת סיכום בסיום הפעלת פונקציה"""
        
        self.counting = len(files_list)
        
        if self.counting < 1:
            print('No matching files or folders found, no changes made!')
        
        else:    
            print(f'Num. of {description}: {self.counting}')



class SimilarDirs(FileManager):

    def __init__(self, root_dirs_list):
        self.root_dirs_list = root_dirs_list
        self.files_list = []
        

    def build_dict(self):          
        for root_dir in self.root_dirs_list: 
            for file in FileManager(root_dir).build_folder_structure():
                
                self.files_list.append(file)
        
        return self.files_list
        
    def find_similar(self):
    
        dirs_found = set()
        
        for path_a, files_a, dir_a in self.files_list:
            for path_b, files_b, dir_b in self.files_list:
                if files_a == files_b and path_a != path_b and dir_a == dir_b:
                    print(f'{path_a} \n {path_b}\n')
                    
                    dirs_found.add((path_a, path_b))
                    
                    
        self.summary_message(dirs_found, 'similar folders found')



if __name__ == "__main__":


    list_dirs = [r"E:\דברים שמתחדשים\חדשים כסליו", r"E:\שמע\כל המוזיקה", r"E:\שמע\מסודר מחדש"]
    

    run1 = SimilarDirs(list_dirs)

    run1.build_dict()
    run1.find_similar()


