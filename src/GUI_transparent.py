from PyQt5.QtWidgets import QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox, QLineEdit, QGroupBox, QPushButton, QMessageBox, QCheckBox, QFrame, QListWidget, QAbstractItemView
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import sys
import os
import pandas as pd

## Add the BLE directory to the path
current_file_path = os.path.abspath(__file__)
current_directory = os.path.dirname(current_file_path)
sys.path.insert(0, os.path.join(os.path.dirname(current_directory),'BLEs'))

## Set some defaults
root_dir = os.path.dirname(current_directory)

## ------------------------------------------------- ##
# Worker thread for data loading
## ------------------------------------------------- ##
class DataLoader(QThread):
    data_loaded = pyqtSignal(pd.DataFrame)

    ## load the material data on the background thread
    def run(self):
        filename = 'material_data.csv'
        df_materials = pd.read_csv(os.path.join(root_dir, 'data', filename))
        new_column_names = {
            'Material': 'mat',
            'Density (g/ccm)': 'density',
            'Hardness (HB)': 'hardness',
            'Yield strength (Mpa)': 'yield',
            'Elongation (%)': 'elongation',
            'Tensile modulus (Gpa)': 'tensile_modulus',
            'Shear modulus (Gpa)': 'shear_modulus',
            'Shear strength (Mpa)': 'shear_strength',
            'Specific heat (J/kg.K)': 'specific_heat',
            'Melting temperature (K)': 'melting_temp'
        }
        df_materials.rename(columns=new_column_names, inplace=True)
        self.data_loaded.emit(df_materials)

## ------------------------------------------------- ##
# Worker thread for package loading
## ------------------------------------------------- ##
class PackageLoader(QThread):
    packages_loaded = pyqtSignal(object)

    def run(self):

        ## Load additional packages
        import numpy as np
        from datetime import datetime
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        from matplotlib.figure import Figure
        import seaborn as sns
        import itertools

        ## Define the plot characteristics
        sns.set_theme()
        colors = sns.color_palette()
        line_styles = ['-', '--', '-.', ':',(0,(3,1,1,1,1)),(0,(3,5,1,5,1,5))]
        color_line_style_pairs = list(zip(colors, line_styles))

        ## Load the ballistic limit scripts
        from BLE_transparent import transparent_performance

        ## Emit the loaded packages
        self.packages_loaded.emit({
            'np': np,
            'datetime': datetime,
            'plt': plt,
            'FigureCanvas': FigureCanvas,
            'NavigationToolbar': NavigationToolbar,
            'Figure': Figure,
            'sns': sns,
            'itertools': itertools,
            'pd': pd,
            'color_line_style_pairs': color_line_style_pairs,
            'transparent_performance': transparent_performance
        })

## ------------------------------------------------- ##
# Define the plot window
## ------------------------------------------------- ##
class PlotWindow(QDialog):
    def __init__(self, parent=None):
        super(PlotWindow, self).__init__(parent)

        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        from matplotlib.figure import Figure

        # Create a Figure and a FigureCanvas
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)

        # Create a navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Set a layout for the window
        self.layout = QVBoxLayout(self)

        # Add the toolbar and the canvas to the layout
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas)

        # Set the layout for the window
        self.setLayout(self.layout)

## ------------------------------------------------- ##
# Define the main GUI window
## ------------------------------------------------- ##
class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

        ## Start the DataLoader thread
        self.data_loader = DataLoader()
        self.data_loader.data_loaded.connect(self.on_data_loaded)
        self.data_loader.start()

        ## Start the PackageLoader thread
        self.package_loader = PackageLoader()
        self.package_loader.packages_loaded.connect(self.on_packages_loaded)
        self.package_loader.start()

    def on_data_loaded(self, df_materials):
        self.df_materials = df_materials

    def on_packages_loaded(self, packages):
        self.packages = packages

    def initUI(self):
        self.layout = QVBoxLayout(self)
        widget_width = 120
        self.setWindowTitle("Single Wall")

        # Define the list of materials
        self.AlMatList = list([
            "AA99.9%",
            "AA1100-O",
            "AA2017-T4",
            "AA2024-T351",
            "AA2219-T87",
            "AA3003-H12",
            "AA3003-H14",
            "AA6061-T651",
            "AA7075-T6"])

        # Define the initial materials
        self.initial_proj_mat = "AA2017-T4"
        self.initial_target_type = "Silica"
        self.initial_failure_type = "Perforate"

        ## ------------------------------------------------- ##
        # First frame (impact conditions)
        ## ------------------------------------------------- ##
        self.frame0 = QGroupBox("Impact conditions", self)
        self.frame0.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame0)

        self.frame0_layout = QGridLayout(self.frame0)

        self.angle_label = QLabel("Angle (deg):", self)
        self.frame0_layout.addWidget(self.angle_label, 1, 0)
        self.angle_entry = QLineEdit(self)
        self.angle_entry.setFixedWidth(widget_width)
        self.frame0_layout.addWidget(self.angle_entry, 1, 1)

        ## ------------------------------------------------- ##
        # Second frame (projectile)
        ## ------------------------------------------------- ##
        self.frame1 = QGroupBox("Projectile", self)
        self.frame1.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame1)

        self.frame1_layout = QGridLayout(self.frame1)

        self.material0_label = QLabel("Material:", self.frame1)
        self.frame1_layout.addWidget(self.material0_label, 0, 0)
        self.material0_dropdown = QComboBox(self)
        self.material0_dropdown.setFixedWidth(widget_width)
        self.material0_dropdown.addItems(self.AlMatList)
        self.material0_dropdown.setCurrentText(self.initial_proj_mat) 
        self.material0_dropdown.currentIndexChanged.connect(self.on_material0_selected)
        self.frame1_layout.addWidget(self.material0_dropdown, 0, 1)

        self.density0_label = QLabel("Density (g/cm³):", self)
        self.frame1_layout.addWidget(self.density0_label, 1, 0)
        self.density0_entry = QLineEdit(self)
        self.density0_entry.setFixedWidth(widget_width)
        # self.density0_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_proj_mat, 'density'].values[0]))
        self.density0_entry.setText("2.8")
        self.frame1_layout.addWidget(self.density0_entry, 1, 1)

        ## ------------------------------------------------- ##
        # Third frame (target)
        ## ------------------------------------------------- ##
        self.frame2 = QGroupBox("Target", self)
        self.frame2.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame2)

        self.frame2_layout = QGridLayout(self.frame2)

        # Create a dropdown to select the material class
        self.target_type_label = QLabel("Material:", self.frame2)
        self.frame2_layout.addWidget(self.target_type_label, 0, 0)
        self.target_type_dropdown = QComboBox(self)
        self.target_type_dropdown.setFixedWidth(widget_width)
        self.target_type_dropdown.addItems(["Silica", "Quartz", "Polycarbonate"])
        self.target_type_dropdown.setCurrentText(self.initial_target_type)
        self.target_type_dropdown.currentIndexChanged.connect(self.on_target_type_selected)
        self.frame2_layout.addWidget(self.target_type_dropdown, 0, 1)

        self.thickness_label = QLabel("Thickness (cm):", self)
        self.frame2_layout.addWidget(self.thickness_label, 2, 0)
        self.thickness_entry = QLineEdit(self)
        self.thickness_entry.setFixedWidth(widget_width)        
        self.frame2_layout.addWidget(self.thickness_entry, 2, 1)
        self.thickness_entry.setEnabled(True)

        self.damage_label = QLabel("Max. damage extent (cm):", self)
        self.frame2_layout.addWidget(self.damage_label, 3, 0)
        self.damage_entry = QLineEdit(self)
        self.damage_entry.setFixedWidth(widget_width)        
        self.frame2_layout.addWidget(self.damage_entry, 3, 1)
        self.damage_entry.setDisabled(True)

        ## ------------------------------------------------- ##
        # Fourth frame (analysis type)
        ## ------------------------------------------------- ##
        self.frame3 = QFrame(self)
        self.frame3.setFrameShape(QFrame.StyledPanel)
        self.frame3.setFrameShadow(QFrame.Raised)

        self.frame3_layout = QGridLayout(self.frame3)

        # Create a dropdown to select the specific target failure threshold
        self.failure_type_label = QLabel("Failure type:", self)
        self.frame3_layout.addWidget(self.failure_type_label, 0, 0)
        self.failure_type_dropdown = QComboBox(self)
        self.failure_type_dropdown.setFixedWidth(widget_width)
        self.failure_type_dropdown.addItems(["Perforate", "Detached spall", "Incipient spall"])
        self.failure_type_dropdown.setCurrentText(self.initial_failure_type)
        self.failure_type_dropdown.currentIndexChanged.connect(self.on_failure_type_selected)
        self.frame3_layout.addWidget(self.failure_type_dropdown, 0, 1)

        # Add the new frame to the main layout
        self.layout.addWidget(self.frame3)

        ## ------------------------------------------------- ##
        # Run button
        ## ------------------------------------------------- ##
        self.run_layout = QHBoxLayout()
        self.save_plot_checkbox = QCheckBox("Save plot", self)
        self.save_data_checkbox = QCheckBox("Save data", self)
        self.run_layout.addWidget(self.save_plot_checkbox)
        self.run_layout.addWidget(self.save_data_checkbox)
        self.run_button = QPushButton("Run", self)
        self.run_button.clicked.connect(self.on_run_button_clicked)
        self.run_layout.addWidget(self.run_button)
        self.layout.addLayout(self.run_layout)

    ## ------------------------------------------------- ##
    def on_material0_selected(self, index):
        selected_material = self.material0_dropdown.itemText(index)
        density = self.df_materials.loc[self.df_materials['mat'] == selected_material, 'density'].values[0]
        self.density0_entry.setText(str(density))       

    ## ------------------------------------------------- ##
    def on_target_type_selected(self, index):
        selected_material = self.target_type_dropdown.itemText(index)
        if selected_material == "Quartz":
            self.failure_type_dropdown.clear()
            self.failure_type_dropdown.addItems(["Perforate","Detached spall","Incipient spall","Damage"])     
        elif selected_material == "Silica":
            self.failure_type_dropdown.clear()
            self.failure_type_dropdown.addItems(["Perforate","Detached spall","Incipient spall","Damage"])     
        elif selected_material == "Polycarbonate":
            self.failure_type_dropdown.clear()
            self.failure_type_dropdown.addItems(["Perforate","Detached spall","Incipient spall"])                                         

    ## ------------------------------------------------- ##
    def on_failure_type_selected(self, index):
        failure_type = self.failure_type_dropdown.itemText(index)
        if failure_type == "Damage":
            self.thickness_entry.setDisabled(True)   
            self.damage_entry.setDisabled(False) 
            self.thickness_entry.setText("")
        else:
            self.thickness_entry.setDisabled(False)   
            self.damage_entry.setDisabled(True)
            self.damage_entry.setText("")

    ## ------------------------------------------------- ##
    def on_run_button_clicked(self):

        color_line_style_cycler = self.packages['itertools'].cycle(self.packages['color_line_style_pairs'])

        try:
            ## Check if any of the text boxes are empty
            if not all([self.angle_entry.text(), self.density0_entry.text()]):
                raise ValueError("All fields must be filled out.")     
            else:
                print("All fields filled.")
        
            data = {
                'proj_mat': self.material0_dropdown.currentText(),
                'proj_density': float(self.density0_entry.text()),  # units = g/cm3
                'angle': float(self.angle_entry.text()),  # units = deg
                'type': self.target_type_dropdown.currentText(), 
                'mode': self.failure_type_dropdown.currentText(), 
                'thickness': float(self.thickness_entry.text()) if self.thickness_entry.text() != "" else 0,  # units = cm
                'max_damage': float(self.damage_entry.text()) if self.damage_entry.text() != "" else 0  # units = cm
            }
            df = pd.DataFrame([data])    

            ## Get the current date and time (for saving output)
            now = self.packages['datetime'].now()
            now_str = now.strftime("%Y%m%d_%H%M%S")

            ## Create a plot window
            self.plot_window = PlotWindow()

            ## Create a plot
            ax = self.plot_window.figure.add_subplot(111)

            ## Call the ballistic limit equation
            velocities = self.packages['np'].linspace(0.1, 15, 150)  # units = km/s
            df_plot = pd.DataFrame(self.packages['np'].repeat(df.values, len(velocities), axis=0), columns=df.columns)
            df_plot['velocity'] = velocities
            pltmax = 0
            df_config = df_plot.iloc[[0]].drop(columns=['velocity']) 
            df_results = df_plot[['velocity']].copy()
            color, line_style = next(color_line_style_cycler)
            df_plot['dc_BLE'] = df_plot.apply(self.packages['transparent_performance'],axis=1)
            ax.plot(df_plot['velocity'],df_plot['dc_BLE'],color=color,linestyle=line_style,label='BLE')
            pltmax = max(pltmax, df_plot['dc_BLE'][len(velocities)/2])
            df_results.insert(len(df_results.columns), 'dc_BLE', df_plot['dc_BLE'])

            ax.set_xlabel('Velocity (km/s)')
            ax.set_ylabel('Projectile diameter (cm)')
            ax.set_ylim(0.0,2*pltmax)  
            ax.legend()

            ## Draw the plot
            self.plot_window.canvas.draw()

            ## Show the plot window
            self.plot_window.show()

            ## If the save_plot_checkbox is checked, save the plot
            if self.save_plot_checkbox.isChecked():
                ## Check if the "results" directory exists, and create it if it doesn't
                results_dir = os.path.join(root_dir, "results")
                if not os.path.exists(results_dir):
                    os.makedirs(results_dir)

                ## Save the plot
                self.plot_window.figure.savefig(os.path.join(root_dir,"results",f"plot_{now_str}.png"))

            ## If the save_data_checkbox is checked, save the velocity and critical diameter data, as well as config data
            if self.save_data_checkbox.isChecked():
                ## Check if the "results" directory exists, and create it if it doesn't
                results_dir = os.path.join(root_dir, "results")
                if not os.path.exists(results_dir):
                    os.makedirs(results_dir)

                df_results.to_csv(os.path.join(root_dir,"results",f"blc_data_{now_str}.csv"), index=False)     
                df_config.to_csv(os.path.join(root_dir,"results",f"config_data_{now_str}.csv"), index=False)                 
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", e.args[0])    

## ------------------------------------------------- ##
# Run the application
## ------------------------------------------------- ##            
try:
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