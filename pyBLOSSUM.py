from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton, QSpacerItem, QSizePolicy
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import Qt
import sys
import subprocess
import os
import time

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

        ## Map configurations to scripts
        self.configuration_to_script = {
            "Whipple shield": "GUI_whipple.py",
            "Sandwich panel": "GUI_sandwichPanel.py",
            "Triple wall": "GUI_tripleWall.py",
            "Stuffed Whipple shield": "GUI_stuffedWhipple.py",
            "Mesh double-bumper": "GUI_meshDB.py",
            "Multi-shock": "GUI_multishock.py",
            "Enhanced MLI": "GUI_enhancedMLI.py",
            "Opaque": "GUI_singleWall.py",
            "Transparent": "GUI_transparent.py",
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
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))  # use busy cursor

        selected_configuration = self.configuration_dropdown.currentText()

        ## Start the corresponding script
        script = self.configuration_to_script[selected_configuration]
        current_file_path = os.path.abspath(__file__)
        current_directory = os.path.dirname(current_file_path)
        script_path = os.path.join(current_directory,'src', script)

        ## Launch the subprocess
        process = subprocess.Popen(["python", script_path],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)  
        process.wait()  # Wait for the subprocess to complete
        QApplication.restoreOverrideCursor()  # restore default cursor

## ------------------------------------------------- ##
# Run the application
## ------------------------------------------------- ##      
if __name__ == "__main__":
    try:
        # Your code here
        app = QApplication(sys.argv)
        window = MyApp()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        # Handle exception
        print(f"An error occurred: {e}")
    finally:
        # This code will run whether an exception occurred or not
        os.system('reset')