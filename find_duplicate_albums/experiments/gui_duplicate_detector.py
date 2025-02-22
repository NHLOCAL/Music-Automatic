import sys, os, glob
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel, QListWidget, QListWidgetItem, 
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QCheckBox, QComboBox
)

from PyQt6.QtGui import QPixmap, QColor, QBrush, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# לעיצוב Material Design
from qt_material import apply_stylesheet

# ייבוא הלוגיקה המקורית – ודא שהקובץ duplicate_detector.py נמצא באותה תיקייה
from duplicate_detector import SelectQuality, MergeFolders, SelectAndThrow

# קונפיגורציה בסיסית של לוגים
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

###############################################################################
# מחלקה לאחסון תוצאות הסריקה והנתונים המשותפים בין רכיבי הממשק
###############################################################################
class DataStore:
    def __init__(self):
        self.comparer = None
        self.organized_info = None
        self.sorted_similar_folders = None
        self.folder_quality_scores = None

data_store = DataStore()

###############################################################################
# Worker לביצוע סריקה ברקע (מניעת הקפאת הממשק)
###############################################################################
class ScanWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)  # ישלח אובייקט עם תוצאות הסריקה

    def __init__(self, folder_paths, preferred_bitrate, log_level, force_rescan, enable_hash):
        super().__init__()
        self.folder_paths = folder_paths
        self.preferred_bitrate = preferred_bitrate
        self.log_level = log_level
        self.force_rescan = force_rescan
        self.enable_hash = enable_hash

    def run(self):
        try:
            self.progress.emit("יוצר מופע של הסריקה...")
            comparer = SelectQuality(
                self.folder_paths,
                self.preferred_bitrate,
                self.log_level,
                self.enable_hash,
                self.force_rescan
            )
            self.progress.emit("מפעיל סריקה (יכול לקחת זמן)...")
            comparer.main()
            organized_info = comparer.get_folders_quality()
            result = {
                'comparer': comparer,
                'organized_info': organized_info,
                'sorted_similar_folders': comparer.sorted_similar_folders,
                'folder_quality_scores': comparer.folder_quality_scores
            }
            self.progress.emit("סריקה הושלמה בהצלחה!")
            self.finished.emit(result)
        except Exception as e:
            self.progress.emit(f"שגיאה במהלך הסריקה: {e}")
            self.finished.emit(None)

###############################################################################
# פונקציה להפקת תמונת אלבום מתיקייה – מחפשת קבצי תמונה נפוצים
###############################################################################
def get_album_cover_pixmap(folder_path, width=64, height=64):
    # רשימת שמות קבצים נפוצים לתמונת אלבום
    possible_names = ["cover.jpg", "folder.jpg", "album_cover.jpg", "cover.png"]
    for name in possible_names:
        path = os.path.join(folder_path, name)
        if os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                return pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return QPixmap()  # תמונה ריקה אם לא נמצא

###############################################################################
# החלון הראשי – ממשק מאוחד המכיל את כל הפונקציונליות
###############################################################################
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("מערכת לכפילויות תיקיות מוזיקה")
        self.setGeometry(100, 100, 1000, 700)
        self.init_ui()

    def init_ui(self):
        mainWidget = QWidget()
        mainLayout = QVBoxLayout()

        # --- אזור בחירת תיקיות ואפשרויות ---
        optionsLayout = QHBoxLayout()
        self.folderList = QListWidget()
        self.folderList.setFixedHeight(100)
        optionsLayout.addWidget(self.folderList, stretch=2)

        btnLayout = QVBoxLayout()
        self.btnAddFolder = QPushButton("בחר תיקייה")
        self.btnAddFolder.clicked.connect(self.add_folder)
        btnLayout.addWidget(self.btnAddFolder)

        self.btnRemoveFolder = QPushButton("הסר תיקייה נבחרת")
        self.btnRemoveFolder.clicked.connect(self.remove_folder)
        btnLayout.addWidget(self.btnRemoveFolder)
        optionsLayout.addLayout(btnLayout, stretch=1)

        mainLayout.addLayout(optionsLayout)

        # אפשרויות סריקה
        formLayout = QHBoxLayout()
        self.comboBitrate = QLineEdit("128")
        formLayout.addWidget(QLabel("ביטרייט מועדף:"))
        formLayout.addWidget(self.comboBitrate)

        self.comboLogLevel = QLineEdit("INFO")
        formLayout.addWidget(QLabel("רמת לוג:"))
        formLayout.addWidget(self.comboLogLevel)

        self.checkForceRescan = QCheckBox("סריקה כפויה")
        formLayout.addWidget(self.checkForceRescan)

        self.checkEnableHash = QCheckBox("הפעלת hash")
        self.checkEnableHash.setChecked(True)
        formLayout.addWidget(self.checkEnableHash)

        mainLayout.addLayout(formLayout)

        # כפתור סריקה, פס התקדמות ותווית סטטוס
        scanLayout = QHBoxLayout()
        self.btnScan = QPushButton("התחל סריקה")
        self.btnScan.clicked.connect(self.start_scan)
        scanLayout.addWidget(self.btnScan)

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 0)
        self.progressBar.hide()
        scanLayout.addWidget(self.progressBar)

        self.statusLabel = QLabel("")
        scanLayout.addWidget(self.statusLabel)
        mainLayout.addLayout(scanLayout)

        # --- אזור תוצאות – טבלה מאוחדת ---
        self.resultsTable = QTableWidget(0, 6)
        self.resultsTable.setHorizontalHeaderLabels(["תיקיה ראשונה", "תיקיה שנייה", "ציון דמיון (%)", "ציון איכות", "תמונת אלבום", "נתיב תיקייה"])
        self.resultsTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        mainLayout.addWidget(self.resultsTable)

        # אזור סינון
        filterLayout = QHBoxLayout()
        filterLayout.addWidget(QLabel("סינון לפי ציון דמיון מינימלי:"))
        self.filterEdit = QLineEdit("0")
        filterLayout.addWidget(self.filterEdit)
        self.btnFilter = QPushButton("סנן")
        self.btnFilter.clicked.connect(self.filter_results)
        filterLayout.addWidget(self.btnFilter)
        mainLayout.addLayout(filterLayout)

        # לחצנים למיזוג ומחיקה – עם אישור
        actionLayout = QHBoxLayout()
        self.btnMerge = QPushButton("מיזוג תיקיות")
        self.btnMerge.clicked.connect(self.merge_folders)
        self.btnMerge.setEnabled(False)
        actionLayout.addWidget(self.btnMerge)

        self.btnDelete = QPushButton("מחיקת תיקיות")
        self.btnDelete.clicked.connect(self.delete_folders)
        self.btnDelete.setEnabled(False)
        actionLayout.addWidget(self.btnDelete)
        mainLayout.addLayout(actionLayout)

        mainWidget.setLayout(mainLayout)
        self.setCentralWidget(mainWidget)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "בחר תיקייה", os.getcwd())
        if folder:
            # בדיקה אם כבר קיימת הרשמה
            existing = [self.folderList.item(i).text() for i in range(self.folderList.count())]
            if folder not in existing:
                self.folderList.addItem(folder)

    def remove_folder(self):
        selected = self.folderList.selectedItems()
        if selected:
            for item in selected:
                self.folderList.takeItem(self.folderList.row(item))

    def start_scan(self):
        # איסוף נתיבי תיקיות מהרשימה
        folder_paths = [self.folderList.item(i).text() for i in range(self.folderList.count())]
        if not folder_paths:
            QMessageBox.warning(self, "שגיאה", "יש לבחור לפחות תיקייה אחת.")
            return

        preferred_bitrate = self.comboBitrate.text().strip()
        log_level = self.comboLogLevel.text().strip()
        force_rescan = self.checkForceRescan.isChecked()
        enable_hash = self.checkEnableHash.isChecked()

        # עדכון סטטוס והפעלת פס התקדמות
        self.statusLabel.setText("מפעיל סריקה ברקע...")
        self.progressBar.show()
        self.btnScan.setEnabled(False)
        self.btnMerge.setEnabled(False)
        self.btnDelete.setEnabled(False)

        # הפעלת Worker לביצוע הסריקה ברקע
        self.scanWorker = ScanWorker(folder_paths, preferred_bitrate, log_level, force_rescan, enable_hash)
        self.scanWorker.progress.connect(self.update_status)
        self.scanWorker.finished.connect(self.scan_finished)
        self.scanWorker.start()

    def update_status(self, message):
        self.statusLabel.setText(message)

    def scan_finished(self, result):
        self.progressBar.hide()
        self.btnScan.setEnabled(True)
        if result:
            data_store.comparer = result['comparer']
            data_store.organized_info = result['organized_info']
            data_store.sorted_similar_folders = result['sorted_similar_folders']
            data_store.folder_quality_scores = result['folder_quality_scores']
            self.statusLabel.setText("סריקה הושלמה בהצלחה!")
            self.populate_results_table()
            # לאפשר פעולות מיזוג ומחיקה לאחר סריקה מוצלחת
            self.btnMerge.setEnabled(True)
            self.btnDelete.setEnabled(True)
        else:
            self.statusLabel.setText("סריקה נכשלה. בדוק את הלוג.")

    def populate_results_table(self):
        self.resultsTable.setRowCount(0)
        if not data_store.sorted_similar_folders:
            return

        for (folder_pair, similarity) in data_store.sorted_similar_folders:
            folder1, folder2 = folder_pair
            sim_score = similarity.get('weighted_score', 0)
            # עבור הצגת איכות – נניח כי יש ערך ציון איכות בתיקייה הראשונה (אם קיים)
            quality = data_store.folder_quality_scores.get(folder1, 0) if data_store.folder_quality_scores else 0

            row = self.resultsTable.rowCount()
            self.resultsTable.insertRow(row)

            itemFolder1 = QTableWidgetItem(folder1)
            itemFolder2 = QTableWidgetItem(folder2)
            itemSim = QTableWidgetItem(f"{sim_score:.2f}")
            itemQuality = QTableWidgetItem(f"{quality:.2f}")

            # עיצוב צבעוני: תיקיות עם ציון דמיון גבוה יקבלו רקע ירוק, איכות גבוהה – כחול
            if sim_score >= 90:
                itemSim.setBackground(QBrush(QColor(144, 238, 144)))  # ירוק בהיר
            elif sim_score < 50:
                itemSim.setBackground(QBrush(QColor(255, 182, 193)))  # ורוד בהיר

            if quality >= 90:
                itemQuality.setBackground(QBrush(QColor(173, 216, 230)))  # כחול בהיר

            # עמודת תמונת אלבום – ננסה להציג תמונת אלבום מהתיקיה הראשונה
            coverLabel = QLabel()
            pixmap = get_album_cover_pixmap(folder1, width=64, height=64)
            if pixmap.isNull():
                coverLabel.setText("אין תמונה")
            else:
                coverLabel.setPixmap(pixmap)
            # עמודת נתיב – נציג את תיקיה ראשונה (לשיקולי נראות)
            itemPath = QTableWidgetItem(folder1)

            self.resultsTable.setItem(row, 0, itemFolder1)
            self.resultsTable.setItem(row, 1, itemFolder2)
            self.resultsTable.setItem(row, 2, itemSim)
            self.resultsTable.setItem(row, 3, itemQuality)
            self.resultsTable.setCellWidget(row, 4, coverLabel)
            self.resultsTable.setItem(row, 5, itemPath)

    def filter_results(self):
        try:
            threshold = float(self.filterEdit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "שגיאה", "יש להזין ערך מספרי לסינון.")
            return

        for row in range(self.resultsTable.rowCount()):
            sim_item = self.resultsTable.item(row, 2)
            if sim_item:
                sim_val = float(sim_item.text())
                self.resultsTable.setRowHidden(row, sim_val < threshold)

    def merge_folders(self):
        if not data_store.comparer or not data_store.sorted_similar_folders:
            QMessageBox.warning(self, "אזהרה", "אין נתונים למיזוג. יש לבצע סריקה תחילה.")
            return

        reply = QMessageBox.question(self, "אישור מיזוג", "האם אתה מאשר לבצע את פעולת המיזוג?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                merger = MergeFolders(
                    data_store.organized_info,
                    data_store.comparer.folder_files,
                    self.comboBitrate.text().strip(),
                    data_store.sorted_similar_folders,
                    self.comboLogLevel.text().strip(),
                    False
                )
                merger.merge()
                QMessageBox.information(self, "הצלחה", "מיזוג תיקיות הושלם בהצלחה.")
            except Exception as e:
                QMessageBox.critical(self, "שגיאה", f"שגיאה במיזוג: {e}")

    def delete_folders(self):
        if not data_store.comparer or not data_store.sorted_similar_folders:
            QMessageBox.warning(self, "אזהרה", "אין נתונים למחיקה. יש לבצע סריקה תחילה.")
            return

        try:
            threshold = float(QMessageBox.getText(self, "סף מחיקה", "הכנס את סף ההתאמה למחיקה (למשל 85):")[0])
        except ValueError:
            QMessageBox.warning(self, "שגיאה", "ערך סף לא תקין.")
            return

        reply = QMessageBox.question(self, "אישור מחיקה", "האם אתה מאשר לבצע את פעולת המחיקה?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import builtins
                builtins.input = lambda prompt="": "y"
                selecter = SelectAndThrow(
                    data_store.organized_info,
                    self.comboBitrate.text().strip(),
                    threshold,
                    data_store.sorted_similar_folders,
                    self.comboLogLevel.text().strip(),
                    data_store.folder_quality_scores,
                    False
                )
                selecter.delete()
                QMessageBox.information(self, "הצלחה", "מחיקת תיקיות הושלמה. עיין בלוגים לפרטים.")
            except Exception as e:
                QMessageBox.critical(self, "שגיאה", f"שגיאה במחיקה: {e}")

###############################################################################
# פונקציית main – הפעלת האפליקציה עם עיצוב Material Design
###############################################################################
def main():
    app = QApplication(sys.argv)
    # הפעלת עיצוב Material Design באמצעות qt-material
    apply_stylesheet(app, theme='light_blue.xml')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
