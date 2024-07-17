from PyQt5.QtWidgets import QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox, QLineEdit, QGroupBox, QPushButton, QMessageBox, QCheckBox, QFrame, QListWidget, QAbstractItemView
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import seaborn as sns
import itertools

current_file_path = os.path.abspath(__file__)
current_directory = os.path.dirname(current_file_path)
sys.path.insert(0, os.path.join(os.path.dirname(current_directory),'BLEs'))
from BLE_MLI import mli_performance

# Set some defaults
sns.set_theme()
root_dir = os.path.dirname(current_directory)

# Define the plot characteristics
colors = sns.color_palette()
line_styles = ['-', '--', '-.', ':',(0,(3,1,1,1,1)),(0,(3,5,1,5,1,5))]
color_line_style_pairs = list(zip(colors, line_styles))

# Load the materials data
filename = 'material_data.xlsx'
df_materials = pd.read_excel(os.path.join(root_dir,'data',filename))

# Define the new column names
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
df_materials.rename(columns=new_column_names,inplace=True)

## ------------------------------------------------- ##
# Define the plot window
## ------------------------------------------------- ##
class PlotWindow(QDialog):
    def __init__(self, parent=None):
        super(PlotWindow, self).__init__(parent)

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

        self.layout = QVBoxLayout(self)
        widget_width = 120
        self.setWindowTitle("MLI")

        # Define the list of materials
        self.AlMatList = list([
            "AA99.9%",
            "AA1100-O",
            "AA2017-T4",
            "AA2024-T4",
            "AA2024-T351",
            "AA2219-T87",
            "AA3003-H12",
            "AA3003-H14",
            "AA6061-T651",
            "AA7075-T6"])

        # Define the initial materials
        self.initial_proj_mat = "AA2017-T4"
        self.initial_target_type = "Baseline"
        self.initial_target_mat = "AA6061-T651"

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

        self.density0_label = QLabel("Density (kg/m³):", self)
        self.frame1_layout.addWidget(self.density0_label, 1, 0)
        self.density0_entry = QLineEdit(self)
        self.density0_entry.setFixedWidth(widget_width)
        self.density0_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_proj_mat, 'density'].values[0]))
        self.frame1_layout.addWidget(self.density0_entry, 1, 1)

        ## ------------------------------------------------- ##
        # Third frame (target)
        ## ------------------------------------------------- ##
        self.frame2 = QGroupBox("MLI", self)
        self.frame2.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame2)

        self.frame2_layout = QGridLayout(self.frame2)

        # Create a dropdown to select the material class
        self.target_type_label = QLabel("MLI type:", self.frame2)
        self.frame2_layout.addWidget(self.target_type_label, 0, 0)
        self.target_type_dropdown = QComboBox(self)
        self.target_type_dropdown.setFixedWidth(widget_width)
        self.target_type_dropdown.addItems(["Baseline", "Toughened", "Enhanced"])
        self.target_type_dropdown.setCurrentText(self.initial_target_type)
        self.target_type_dropdown.currentIndexChanged.connect(self.on_target_type_selected)
        self.frame2_layout.addWidget(self.target_type_dropdown, 0, 1)

        # Add a note at the bottom of the frame
        self.note_label = QLabel("NOTE: Assumes standoff between MLI and hull", self)
        self.note_label.setStyleSheet("font-size: 10px;")  # Set the font size to 10px
        self.frame2_layout.addWidget(self.note_label, 1, 0, 1, 2)  # Span the label across two columns    

        # Build the entry boxes
        self.bumperAD_label = QLabel("Bumper AD (g/cm²):", self)
        self.frame2_layout.addWidget(self.bumperAD_label, 2, 0)
        self.bumperAD_entry = QLineEdit(self)
        self.bumperAD_entry.setFixedWidth(widget_width)             
        self.frame2_layout.addWidget(self.bumperAD_entry, 2, 1)

        self.MLIad_label = QLabel("MLI AD (g/cm²):", self)
        self.frame2_layout.addWidget(self.MLIad_label, 3, 0)
        self.MLIad_entry = QLineEdit(self)
        self.MLIad_entry.setFixedWidth(widget_width)             
        self.frame2_layout.addWidget(self.MLIad_entry, 3, 1)
        self.MLIad_entry.setEnabled(False)

        self.material1_label = QLabel("Wall material:", self.frame2)
        self.frame2_layout.addWidget(self.material1_label, 4, 0)
        self.material1_dropdown = QComboBox(self)
        self.material1_dropdown.setFixedWidth(widget_width)
        self.material1_dropdown.addItems(self.AlMatList)
        self.material1_dropdown.setCurrentText(self.initial_target_mat) 
        self.material1_dropdown.currentIndexChanged.connect(self.on_material1_selected)
        self.frame2_layout.addWidget(self.material1_dropdown, 4, 1)

        self.wallThickness_label = QLabel("Wall thickness (cm):", self)
        self.frame2_layout.addWidget(self.wallThickness_label, 5, 0)
        self.wallThickness_entry = QLineEdit(self)
        self.wallThickness_entry.setFixedWidth(widget_width)        
        self.frame2_layout.addWidget(self.wallThickness_entry, 5, 1)
        
        self.density1_label = QLabel("Wall density (kg/m³)):", self)
        self.frame2_layout.addWidget(self.density1_label, 6, 0)
        self.density1_entry = QLineEdit(self)
        self.density1_entry.setFixedWidth(widget_width)
        self.density1_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_target_mat, 'density'].values[0]))
        self.frame2_layout.addWidget(self.density1_entry, 6, 1)

        self.wallAD_label = QLabel("Wall AD (g/cm²):", self)
        self.frame2_layout.addWidget(self.wallAD_label, 7, 0)
        self.wallAD_entry = QLineEdit(self)
        self.wallAD_entry.setFixedWidth(widget_width)             
        self.frame2_layout.addWidget(self.wallAD_entry, 7, 1)

        # Add a note at the bottom of the frame
        self.note_label = QLabel("NOTE: Need to specify wall density and either thickness or areal density", self)
        self.note_label.setStyleSheet("font-size: 10px;")  # Set the font size to 10px
        self.frame2_layout.addWidget(self.note_label, 8, 0, 1, 2)  # Span the label across two columns             

        self.totalThickness_label = QLabel("Total thickness (cm):", self)
        self.frame2_layout.addWidget(self.totalThickness_label, 9, 0)
        self.totalThickness_entry = QLineEdit(self)
        self.totalThickness_entry.setFixedWidth(widget_width)             
        self.frame2_layout.addWidget(self.totalThickness_entry, 9, 1)
        self.totalThickness_entry.setEnabled(False)

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
        density = df_materials.loc[df_materials['mat'] == selected_material, 'density'].values[0]
        self.density0_entry.setText(str(density))

    ## ------------------------------------------------- ##
    def on_material1_selected(self, index):
        selected_material = self.material0_dropdown.itemText(index)
        self.density1_entry.setText(str(df_materials.loc[df_materials['mat'] == selected_material, 'density'].values[0]))       

    ## ------------------------------------------------- ##
    def on_target_type_selected(self, index):
        selected_mli = self.target_type_dropdown.itemText(index)
        if selected_mli == "Baseline":
            self.MLIad_entry.setDisabled(True)   
            self.totalThickness_entry.setDisabled(True)
            self.MLIad_entry.setText("")   
            self.totalThickness_entry.setText("")     
        elif selected_mli == "Toughened":
            self.MLIad_entry.setDisabled(True)   
            self.totalThickness_entry.setDisabled(True)
            self.MLIad_entry.setText("")   
            self.totalThickness_entry.setText("")          
        elif selected_mli == "Enhanced":
            self.MLIad_entry.setDisabled(False)   
            self.totalThickness_entry.setDisabled(False)
            self.MLIad_entry.setText("")   
            self.totalThickness_entry.setText("")                   

    ## ------------------------------------------------- ##
    def on_run_button_clicked(self):

        color_line_style_cycler = itertools.cycle(color_line_style_pairs)

        try:
            # Check if the wall AD and thickness are directly specified, if not calculate them
            if self.wallAD_entry.text() == "":
                self.wallAD_entry.setText(str(float(self.wallThickness_entry.text())*float(self.density1_entry.text())))
            elif self.wallThickness_entry.text() == "":
                self.wallThickness_entry.setText(str(float(self.wallAD_entry.text())/float(self.density1_entry.text())))

            # Check some of the configuration-dependent fields
            if self.totalThickness_entry.text() == "" and self.target_type_dropdown.currentText() != "Enhanced":
                self.totalThickness_entry.setText("0")
            if self.MLIad_entry.text() == "" and self.target_type_dropdown.currentText() != "Enhanced":
                self.MLIad_entry.setText("0")                

            # Check if any of the text boxes are empty
            if not all([self.angle_entry.text(), self.density0_entry.text(),self.wallThickness_entry.text(), 
                        self.density1_entry.text(), self.MLIad_entry.text(),self.bumperAD_entry.text(),
                        self.wallAD_entry.text(),self.totalThickness_entry.text()]):
                raise ValueError("All fields must be filled out.")     
            else:
                print("All fields filled.")

            data = {
                'proj_mat': self.material0_dropdown.currentText(),
                'proj_density': float(self.density0_entry.text()),
                'angle': float(self.angle_entry.text()),
                'type': self.target_type_dropdown.currentText(), 
                'target_mat': self.material1_dropdown.currentText(), 
                'wall_thick': float(self.wallThickness_entry.text()),
                'wall_density': float(self.density1_entry.text()),                
                'bumper_AD': float(self.bumperAD_entry.text()),
                'wall_AD': float(self.wallAD_entry.text()),
                'MLI_AD': float(self.MLIad_entry.text()),
                'thickness': float(self.totalThickness_entry.text())
            }

            ## add material type code
            if self.target_type_dropdown.currentText() == "Baseline":
                data['type'] = 'Baseline' 
            elif self.target_type_dropdown.currentText() == "Toughened":                
                data['type'] = 'Toughened'
            elif self.target_type_dropdown.currentText() == "Enhanced":                
                data['type'] = 'Enhanced'

            df = pd.DataFrame([data])    

            # Get the current date and time (for saving output)
            now = datetime.now()
            now_str = now.strftime("%Y%m%d_%H%M%S")

            # Create a plot window
            self.plot_window = PlotWindow()

            # Create a plot
            ax = self.plot_window.figure.add_subplot(111)

            # Call the ballistic limit equation
            velocities = np.linspace(0.1, 15, 150)
            df_plot = pd.DataFrame(np.repeat(df.values, len(velocities), axis=0), columns=df.columns)
            df_plot['velocity'] = velocities
            pltmax = 0
            df_config = df_plot.iloc[[0]].drop(columns=['velocity']) 
            df_results = df_plot[['velocity']].copy()
            color, line_style = next(color_line_style_cycler)
            df_plot['dc_BLE'] = df_plot.apply(mli_performance,axis=1)
            ax.plot(df_plot['velocity'],df_plot['dc_BLE'],color=color,linestyle=line_style,label='BLE')
            pltmax = max(pltmax, df_plot['dc_BLE'][len(velocities)/2])
            df_results.insert(len(df_results.columns), 'dc_BLE', df_plot['dc_BLE'])

            ax.set_xlabel('Velocity (km/s)')
            ax.set_ylabel('Projectile diameter (cm)')
            ax.set_ylim(0.0,2*pltmax)  
            ax.legend()

            # Draw the plot
            self.plot_window.canvas.draw()

            # Show the plot window
            self.plot_window.show()

            # If the save_plot_checkbox is checked, save the plot
            if self.save_plot_checkbox.isChecked():
                # Check if the "results" directory exists, and create it if it doesn't
                results_dir = os.path.join(root_dir, "results")
                if not os.path.exists(results_dir):
                    os.makedirs(results_dir)

                # Save the plot
                self.plot_window.figure.savefig(os.path.join(root_dir,"results",f"plot_{now_str}.png"))

            # If the save_data_checkbox is checked, save the velocity and critical diameter data, as well as config data
            if self.save_data_checkbox.isChecked():
                # Check if the "results" directory exists, and create it if it doesn't
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