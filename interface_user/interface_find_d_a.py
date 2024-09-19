from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton,
    QLabel, QFileDialog, QTextEdit, QWidget, QHBoxLayout,
    QListWidget, QListWidgetItem, QMessageBox
)
from find_duplic_albums import FolderComparer


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folder Comparison Tool")
        self.folder_paths = []

        main_widget = QWidget()
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

        self.label = QLabel("Selected Folder(s):")
        layout.addWidget(self.label)

        self.output_text = QTextEdit()
        layout.addWidget(self.output_text)

        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        self.select_button = QPushButton("Select Folder")
        self.select_button.clicked.connect(self.select_folder)
        button_layout.addWidget(self.select_button)

        self.execute_button = QPushButton("Execute Comparison")
        self.execute_button.clicked.connect(self.execute_comparison)
        button_layout.addWidget(self.execute_button)

        self.similar_folders_list = QListWidget()
        layout.addWidget(self.similar_folders_list)

        self.similar_folders = {}

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.folder_paths.append(folder_path)
            self.output_text.append(f"Folder selected: {folder_path}")

    def execute_comparison(self):
        if not self.folder_paths:
            self.output_text.append("No folder selected!")
            return

        self.output_text.append("Executing comparison...")
        comparer = FolderComparer(self.folder_paths)
        folder_files = comparer.get_file_lists()  # Get file lists first
        self.similar_folders = comparer.find_similar_folders(folder_files)  # Pass file lists to find similar folders
        self.update_similar_folders_list()

    def update_similar_folders_list(self):
        self.similar_folders_list.clear()
        for folder_pair, similarities in self.similar_folders.items():
            folder_path, other_folder_path = folder_pair
            item = QListWidgetItem(f"Similar folders: {folder_path} and {other_folder_path}")
            item.setData(1, folder_pair)  # Storing folder pair data
            self.similar_folders_list.addItem(item)
        
        self.similar_folders_list.itemClicked.connect(self.show_similarity_details)

    def show_similarity_details(self, item):
        folder_pair = item.data(1)
        similarities = self.similar_folders[folder_pair]
        details_dialog = QMessageBox()
        details_dialog.setWindowTitle("Similarity Details")
        details_dialog.setText(f"Similar folders: {folder_pair[0]} and {folder_pair[1]}\nSimilarity scores:")
        details_dialog.setDetailedText("\n".join([f"{param.capitalize()}: {score}" for param, score in similarities.items()]))
        details_dialog.exec()


def main():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
