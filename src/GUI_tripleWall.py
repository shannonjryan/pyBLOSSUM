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
from BLE_SRL import SRL_triple_performance

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
        self.setWindowTitle("Triple wall shield")

        # Define the list of materials
        self.AlMatList = list([
            "AA99.9%",
            "AA1100-O",
            "AA1100-H14",
            "AA2017-T4",
            "AA2024-T351",
            "AA2024-T4",
            "AA2219-T87",
            "AA3003-H12",
            "AA3003-H14",
            "AA6061-T651",
            "AA7075-T6"])

        # Define the initial materials
        self.initial_proj_mat = "AA2017-T4"
        self.initial_outerBumper_mat = "AA6061-T651"
        self.initial_innerBumper_mat = "AA6061-T651"
        self.initial_wall_mat = "AA6061-T651"

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
        # Second frame (outer bumper plate)
        ## ------------------------------------------------- ##
        self.frame2 = QGroupBox("Outer bumper plate", self)
        self.frame2.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame2)

        self.frame2_layout = QGridLayout(self.frame2)

        self.material1_label = QLabel("Material:", self.frame2)
        self.frame2_layout.addWidget(self.material1_label, 0, 0)
        self.material1_dropdown = QComboBox(self)
        self.material1_dropdown.setFixedWidth(widget_width)
        self.material1_dropdown.addItems(self.AlMatList + ["CFRP", "Other"])
        self.material1_dropdown.setCurrentText(self.initial_outerBumper_mat) 
        self.material1_dropdown.currentIndexChanged.connect(self.on_material1_selected)
        self.frame2_layout.addWidget(self.material1_dropdown, 0, 1)

        self.thickness1_label = QLabel("Thickness (mm):", self)
        self.frame2_layout.addWidget(self.thickness1_label, 1, 0)
        self.thickness1_entry = QLineEdit(self)
        self.thickness1_entry.setFixedWidth(widget_width)
        self.frame2_layout.addWidget(self.thickness1_entry, 1, 1)

        self.density1_label = QLabel("Density (kg/m³):", self)
        self.frame2_layout.addWidget(self.density1_label, 2, 0)
        self.density1_entry = QLineEdit(self)
        self.density1_entry.setFixedWidth(widget_width)
        self.density1_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_outerBumper_mat, 'density'].values[0]))
        self.frame2_layout.addWidget(self.density1_entry, 2, 1)

        self.standoff1_label = QLabel("Standoff to inner bumper (mm):", self)
        self.frame2_layout.addWidget(self.standoff1_label, 3, 0)
        self.standoff1_entry = QLineEdit(self)
        self.standoff1_entry.setFixedWidth(widget_width)
        self.frame2_layout.addWidget(self.standoff1_entry, 3, 1)        

        self.MLI_label = QLabel("MLI AD (g/cm²):", self)
        self.frame2_layout.addWidget(self.MLI_label, 4, 0)
        self.MLI_entry = QLineEdit(self)
        self.MLI_entry.setFixedWidth(widget_width)             
        self.frame2_layout.addWidget(self.MLI_entry, 4, 1)

        ## ------------------------------------------------- ##
        # Third frame (inner bumper plate)
        ## ------------------------------------------------- ##
        self.frame3 = QGroupBox("Inner bumper plate", self)
        self.frame3.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame3)

        self.frame3_layout = QGridLayout(self.frame3)

        self.material2_label = QLabel("Material:", self.frame3)
        self.frame3_layout.addWidget(self.material2_label, 0, 0)
        self.material2_dropdown = QComboBox(self)
        self.material2_dropdown.setFixedWidth(widget_width)        
        self.material2_dropdown.addItems(self.AlMatList + ["CFRP", "Other"])
        self.material2_dropdown.setCurrentText(self.initial_innerBumper_mat) 
        self.material2_dropdown.currentIndexChanged.connect(self.on_material2_selected)
        self.frame3_layout.addWidget(self.material2_dropdown, 0, 1)

        self.thickness2_label = QLabel("Thickness (mm):", self)
        self.frame3_layout.addWidget(self.thickness2_label, 1, 0)
        self.thickness2_entry = QLineEdit(self)
        self.thickness2_entry.setFixedWidth(widget_width)        
        self.frame3_layout.addWidget(self.thickness2_entry, 1, 1)

        self.density2_label = QLabel("Density (kg/m³):", self)
        self.frame3_layout.addWidget(self.density2_label, 2, 0)
        self.density2_entry = QLineEdit(self)
        self.density2_entry.setFixedWidth(widget_width)
        self.density2_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_innerBumper_mat, 'density'].values[0]))
        self.frame3_layout.addWidget(self.density2_entry, 2, 1)

        self.standoff2_label = QLabel("Standoff to rear wall (mm):", self)
        self.frame3_layout.addWidget(self.standoff2_label, 3, 0)
        self.standoff2_entry = QLineEdit(self)
        self.standoff2_entry.setFixedWidth(widget_width)
        self.frame3_layout.addWidget(self.standoff2_entry, 3, 1)           

        ## ------------------------------------------------- ##
        # Fourth frame (rear wall)
        ## ------------------------------------------------- ##
        self.frame4 = QGroupBox("Rear wall", self)
        self.frame4.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame4)

        self.frame4_layout = QGridLayout(self.frame4)

        self.material3_label = QLabel("Material:", self.frame4)
        self.frame4_layout.addWidget(self.material3_label, 0, 0)
        self.material3_dropdown = QComboBox(self)
        self.material3_dropdown.setFixedWidth(widget_width)        
        self.material3_dropdown.addItems(self.AlMatList)
        self.material3_dropdown.setCurrentText(self.initial_wall_mat) 
        self.material3_dropdown.currentIndexChanged.connect(self.on_material3_selected)
        self.frame4_layout.addWidget(self.material3_dropdown, 0, 1)

        self.thickness3_label = QLabel("Thickness (mm):", self)
        self.frame4_layout.addWidget(self.thickness3_label, 1, 0)
        self.thickness3_entry = QLineEdit(self)
        self.thickness3_entry.setFixedWidth(widget_width)        
        self.frame4_layout.addWidget(self.thickness3_entry, 1, 1)

        self.density3_label = QLabel("Density (kg/m³):", self)
        self.frame4_layout.addWidget(self.density3_label, 2, 0)
        self.density3_entry = QLineEdit(self)
        self.density3_entry.setFixedWidth(widget_width)
        self.density3_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_wall_mat, 'density'].values[0]))
        self.frame4_layout.addWidget(self.density3_entry, 2, 1)

        self.yield3_label = QLabel("Yield strength (MPa):", self)
        self.frame4_layout.addWidget(self.yield3_label, 3, 0)
        self.yield3_entry = QLineEdit(self)
        self.yield3_entry.setFixedWidth(widget_width)        
        self.yield3_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_wall_mat, 'yield'].values[0]))
        self.frame4_layout.addWidget(self.yield3_entry, 3, 1)

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
        selected_material = self.material1_dropdown.itemText(index)
        if selected_material != 'CFRP' and selected_material != 'Other':
            density1 = df_materials.loc[df_materials['mat'] == selected_material, 'density'].values[0]
            self.density1_entry.setText(str(density1))
        else:
            self.density1_entry.setText("")

    ## ------------------------------------------------- ##
    def on_material2_selected(self, index):
        selected_material = self.material2_dropdown.itemText(index)
        if selected_material != 'CFRP' and selected_material != 'Other':
            density2 = df_materials.loc[df_materials['mat'] == selected_material, 'density'].values[0]
            self.density2_entry.setText(str(density2))
        else:
            self.density2_entry.setText("")            

    ## ------------------------------------------------- ##
    def on_material3_selected(self, index):
        selected_material = self.material3_dropdown.itemText(index)
        density3 = df_materials.loc[df_materials['mat'] == selected_material, 'density'].values[0]
        yield3 = df_materials.loc[df_materials['mat'] == selected_material, 'yield'].values[0]
        self.density3_entry.setText(str(density3))
        self.yield3_entry.setText(str(yield3))          

    ## ------------------------------------------------- ##
    def on_run_button_clicked(self):
        color_line_style_cycler = itertools.cycle(color_line_style_pairs)

        try:
            # If MLI_AD field is left empty, fill with '0'
            if not self.MLI_entry.text():
                self.MLI_entry.setText("0")

            # Check if any of the text boxes are empty
            if not all([self.angle_entry.text(), self.density0_entry.text(),
                        self.thickness1_entry.text(), self.density1_entry.text(), self.standoff1_entry.text(),
                        self.thickness2_entry.text(), self.density2_entry.text(), self.standoff2_entry.text(),
                        self.thickness3_entry.text(), self.density3_entry.text(), self.yield3_entry.text()]):
                raise ValueError("All fields must be filled out.")
            else:
                print("All fields filled.")

            data = {
                'proj_mat': self.material0_dropdown.currentText(),
                'proj_density': float(self.density0_entry.text()),
                'angle': float(self.angle_entry.text()),
                'outerBumper_mat': self.material1_dropdown.currentText(), 
                'outerBumper_thick': float(self.thickness1_entry.text()),
                'outerBumper_density': float(self.density1_entry.text()),
                'standoff1': float(self.standoff1_entry.text()),
                'innerBumper_mat': self.material2_dropdown.currentText(), 
                'innerBumper_thick': float(self.thickness2_entry.text()),
                'innerBumper_density': float(self.density2_entry.text()),
                'standoff2': float(self.standoff2_entry.text()),                
                'wall_mat': self.material3_dropdown.currentText(),
                'wall_thick': float(self.thickness3_entry.text()),
                'wall_density': float(self.density3_entry.text()),
                'wall_yield': float(self.yield3_entry.text())*0.145038,  # convert MPa to ksi
                'AD_MLI': float(self.MLI_entry.text())
            }
            df = pd.DataFrame([data])

            # Get the current date and time
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
            df_plot['dc_BLE'] = df_plot.apply(SRL_triple_performance,axis=1)
            ax.plot(df_plot['velocity'],df_plot['dc_BLE'],color=color,linestyle=line_style,label='BLE')
            pltmax = max(pltmax, df_plot['dc_BLE'][len(velocities)/2])
            df_results.insert(len(df_results.columns), 'dc_BLE', df_plot['dc_BLE'])
            
            ax.set_xlabel('Velocity (km/s)')
            ax.set_ylabel('Projectile diameter (mm)')
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

                self.plot_window.figure.savefig(os.path.join(root_dir,"results",f"plot_{now_str}.png"))

            # If the save_data_checkbox is checked, save the velocity and critical diameter data, as well as config data
            if self.save_data_checkbox.isChecked():
                # Check if the "results" directory exists, and create it if it doesn't
                results_dir = os.path.join(root_dir, "results")
                if not os.path.exists(results_dir):
                    os.makedirs(results_dir)
                
                df_config['wall_yield'] = df_config['wall_yield']/0.145038  # convert ksi to MPa
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