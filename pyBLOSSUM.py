from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton, QSpacerItem, QSizePolicy, QMessageBox
from PyQt5.QtCore import Qt, QTimer
from importlib import import_module
import sys

from src.gui_support import warm_analysis_libraries

class MyApp(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout(self)

        self.setWindowTitle("pyBLOSSUM")
        # self.setMinimumSize(400, 300)  # Set a minimum size for the window
        dropdown_width = 150  # Set a fixed width

        ## dropdown box for selecting the shield category
        self.shield_type_layout = QHBoxLayout()
        self.shield_type_label = QLabel("Shield type:", self)
        self.shield_type_layout.addWidget(self.shield_type_label)
        self.shield_type_dropdown = QComboBox(self)
        self.shield_type_dropdown.setFixedWidth(dropdown_width)
        self.shield_type_dropdown.addItems(["Single wall", "Double wall", "Advanced", "Thermal protection"])
        self.shield_type_dropdown.currentIndexChanged.connect(self.on_shield_type_selected)
        self.shield_type_layout.addWidget(self.shield_type_dropdown)
        self.layout.addLayout(self.shield_type_layout)

        ## dropdown box for selecting the configuration
        self.configuration_layout = QHBoxLayout()
        self.configuration_label = QLabel("Configuration:", self)
        self.configuration_layout.addWidget(self.configuration_label)
        self.configuration_dropdown = QComboBox(self)
        self.configuration_dropdown.setFixedWidth(dropdown_width)
        self.configuration_dropdown.addItems(["Opaque", "Transparent"])
        self.configuration_layout.addWidget(self.configuration_dropdown)
        self.layout.addLayout(self.configuration_layout)

        ## action button to perform the analysis
        self.analyse_button_layout = QHBoxLayout()
        self.analyse_button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.analyse_button = QPushButton("Analyse", self)
        self.analyse_button.clicked.connect(self.on_analyse_button_clicked)
        self.analyse_button_layout.addWidget(self.analyse_button)
        self.layout.addLayout(self.analyse_button_layout)

        self.analysis_windows = set()
        self.configuration_to_module = {
            "Whipple shield": "src.GUI_whipple",
            "Sandwich panel": "src.GUI_sandwichPanel",
            "Triple wall": "src.GUI_tripleWall",
            "Stuffed Whipple shield": "src.GUI_stuffedWhipple",
            "Mesh double-bumper": "src.GUI_meshDB",
            "Multi-shock": "src.GUI_multishock",
            "Enhanced MLI": "src.GUI_enhancedMLI",
            "Opaque": "src.GUI_singleWall",
            "Transparent": "src.GUI_transparent",
        }

    def on_shield_type_selected(self, index):
        selected_shield_type = self.shield_type_dropdown.itemText(index)

        ## Populate the configuration dropdown based on the selected shield type
        if selected_shield_type == "Single wall":
            self.configuration_dropdown.clear()
            self.configuration_dropdown.addItems(["Opaque", "Transparent"])
        elif selected_shield_type == "Double wall":
            self.configuration_dropdown.clear()
            self.configuration_dropdown.addItems(["Whipple shield", "Sandwich panel"])
        elif selected_shield_type == "Advanced":
            self.configuration_dropdown.clear()
            self.configuration_dropdown.addItems(["Triple wall", "Stuffed Whipple shield", "Mesh double-bumper", "Multi-shock"])
        elif selected_shield_type == "Thermal protection":
            self.configuration_dropdown.clear()
            self.configuration_dropdown.addItems(["Enhanced MLI"])

    def on_analyse_button_clicked(self):
        selected_configuration = self.configuration_dropdown.currentText()

        try:
            module = import_module(self.configuration_to_module[selected_configuration])
            window = module.MyApp()
        except (ImportError, OSError, ValueError, KeyError) as error:
            QMessageBox.critical(self, "Launch error", f"Could not open the analysis window.\n{error}")
            return
        window.setAttribute(Qt.WA_DeleteOnClose)
        self.analysis_windows.add(window)
        window.destroyed.connect(lambda: self.analysis_windows.discard(window))
        window.show()

## ------------------------------------------------- ##
# Run the application
## ------------------------------------------------- ##      
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        window = MyApp()
        window.show()
        QTimer.singleShot(0, warm_analysis_libraries)
        sys.exit(app.exec_())
    except Exception as e:
        # Handle exception
        print(f"An error occurred: {e}")
