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
from BLE_multishock import multishockHybrid_performance, multishockAl_performance, multishockKevlar_performance, multishockNextel_performance

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
        self.setWindowTitle("Multi-shock shield")

        # Define the list of materials
        self.AlMatList = list([
            "AA99.9%",
            "AA1100-O",
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
        # self.initial_bumper_mat = "AA6061-T651"
        self.initial_wall_mat = "Kevlar"
        self.initial_target_type = "Kevlar rear wall"

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
        # Third frame - shield type
        ## ------------------------------------------------- ##
        self.frame2 = QGroupBox("Shield type", self)
        self.frame2.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame2)

        self.frame2_layout = QGridLayout(self.frame2)

        # Create a dropdown to select the shield class
        self.target_type_label = QLabel("Shield type:", self.frame2)
        self.frame2_layout.addWidget(self.target_type_label, 0, 0)
        self.target_type_dropdown = QComboBox(self)
        self.target_type_dropdown.setFixedWidth(widget_width)
        self.target_type_dropdown.addItems(["Nextel rear wall","Kevlar rear wall","Aluminium rear wall","Hybrid shield"])
        self.target_type_dropdown.setCurrentText(self.initial_target_type)
        self.target_type_dropdown.currentIndexChanged.connect(self.on_target_type_selected)
        self.frame2_layout.addWidget(self.target_type_dropdown, 0, 1)

        ## ------------------------------------------------- ##
        # Third frame - bumper plates
        ## ------------------------------------------------- ##
        self.frame3 = QGroupBox("Bumper plates", self)
        self.frame3.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame3)

        self.frame3_layout = QGridLayout(self.frame3)



        self.bumperAD_label = QLabel("Total bumper AD (g/cm<sup>2</sup>):", self)
        self.frame3_layout.addWidget(self.bumperAD_label, 2, 0)
        self.bumperAD_entry = QLineEdit(self)
        self.bumperAD_entry.setFixedWidth(widget_width)
        self.frame3_layout.addWidget(self.bumperAD_entry, 2, 1)

        self.material1_label = QLabel("Wall material:", self.frame3)
        self.frame3_layout.addWidget(self.material1_label, 3, 0)
        self.material1_dropdown = QComboBox(self)
        self.material1_dropdown.setFixedWidth(widget_width)        
        self.material1_dropdown.addItems(self.AlMatList)
        self.material1_dropdown.addItems(["Nextel","Kevlar"])
        self.material1_dropdown.setCurrentText(self.initial_wall_mat) 
        self.material1_dropdown.currentIndexChanged.connect(self.on_material1_selected)
        self.frame3_layout.addWidget(self.material1_dropdown, 3, 1)    
        self.material1_dropdown.setDisabled(True)

        self.thickness1_label = QLabel("Wall thickness (cm):", self)
        self.frame3_layout.addWidget(self.thickness1_label, 4, 0)
        self.thickness1_entry = QLineEdit(self)
        self.thickness1_entry.setFixedWidth(widget_width)
        self.frame3_layout.addWidget(self.thickness1_entry, 4, 1)
        self.thickness1_entry.setDisabled(True)

        self.density1_label = QLabel("Density (kg/m³):", self)
        self.frame3_layout.addWidget(self.density1_label, 5, 0)
        self.density1_entry = QLineEdit(self)
        self.density1_entry.setFixedWidth(widget_width)
        self.frame3_layout.addWidget(self.density1_entry, 5, 1)
        self.density1_entry.setDisabled(True)

        self.yield1_label = QLabel("Wall yield (MPa):", self)
        self.frame3_layout.addWidget(self.yield1_label, 6, 0)
        self.yield1_entry = QLineEdit(self)
        self.yield1_entry.setFixedWidth(widget_width)
        self.frame3_layout.addWidget(self.yield1_entry, 6, 1)
        self.yield1_entry.setDisabled(True) 

        self.wallAD_label = QLabel("Wall AD (g/cm<sup>2</sup>):", self)
        self.frame3_layout.addWidget(self.wallAD_label, 7, 0)
        self.wallAD_entry = QLineEdit(self)
        self.wallAD_entry.setFixedWidth(widget_width)
        self.frame3_layout.addWidget(self.wallAD_entry, 7, 1)    

        # Add a note at the bottom of the frame
        self.note_label = QLabel("NOTE: Need to specify either AD or density and thickness", self)
        self.note_label.setStyleSheet("font-size: 10px;")  # Set the font size to 10px
        self.frame3_layout.addWidget(self.note_label, 8, 0, 1, 2)  # Span the label across two columns             

        self.standoff_label = QLabel("Total shield thickness (cm):", self)
        self.frame3_layout.addWidget(self.standoff_label, 9, 0)
        self.standoff_entry = QLineEdit(self)
        self.standoff_entry.setFixedWidth(widget_width)        
        self.frame3_layout.addWidget(self.standoff_entry, 9, 1)    

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
        density1 = df_materials.loc[df_materials['mat'] == selected_material, 'density'].values[0]
        self.density1_entry.setText(str(density1))     
        yield1 = df_materials.loc[df_materials['mat'] == selected_material, 'yield'].values[0]
        self.yield1_entry.setText(str(yield1))

    ## ------------------------------------------------- ##
    def on_target_type_selected(self, index):
        
        target_type = self.target_type_dropdown.itemText(index)
        if target_type == "Kevlar rear wall":
            self.material1_dropdown.setDisabled(True)
            self.thickness1_entry.setDisabled(True)
            self.density1_entry.setDisabled(True)   
            self.yield1_entry.setDisabled(True)     
            self.thickness1_entry.setText("")
            self.density1_entry.setText("")
            self.yield1_entry.setText("")
        elif target_type == "Nextel rear wall":
            self.material1_dropdown.setDisabled(True)
            self.thickness1_entry.setDisabled(True)
            self.density1_entry.setDisabled(True)   
            self.yield1_entry.setDisabled(True)    
            self.thickness1_entry.setText("")
            self.density1_entry.setText("")
            self.yield1_entry.setText("")
        elif target_type == "Aluminium rear wall":
            self.material1_dropdown.setDisabled(False)   
            self.thickness1_entry.setDisabled(False)
            self.density1_entry.setDisabled(False)   
            self.yield1_entry.setDisabled(False)   
            self.material1_dropdown.setCurrentText("AA2219-T87")    
        elif target_type == "Hybrid shield":
            self.material1_dropdown.setDisabled(False)
            self.thickness1_entry.setDisabled(False)
            self.density1_entry.setDisabled(False)   
            self.yield1_entry.setDisabled(False)   
            self.material1_dropdown.setCurrentText("AA2219-T87")

    ## ------------------------------------------------- ##
    def on_run_button_clicked(self):
        color_line_style_cycler = itertools.cycle(color_line_style_pairs) 

        try:           
            # Check that the rear wall fields have been correctly populated, fill the 
            if self.wallAD_entry.text() == "" and (self.density1_entry.text() == "" or self.thickness1_entry.text() == ""):
                raise ValueError("Please enter either the wall AD or the wall density and thickness.")
            elif self.wallAD_entry.text() != "" and (self.density1_entry.text() != "" or self.thickness1_entry.text() != ""):
                raise ValueError("Please enter either the wall AD or the wall density and thickness, not both.")
            elif self.yield1_entry.text() == "" and (self.target_type_dropdown.currentText() == "Aluminium rear wall" or self.target_type_dropdown.currentText() == "Hybrid shield"):
                raise ValueError("Please enter the rear wall yield strength.")            

            # Check if any of the text boxes are empty
            if not all([self.angle_entry.text(), self.density0_entry.text(),self.bumperAD_entry.text(),self.standoff_entry.text()]):
                raise ValueError("All fields must be filled out.")
            else:
                print("All fields filled.")

            ## define the input data
            data = {
                'proj_mat': self.material0_dropdown.currentText(),
                'proj_density': float(self.density0_entry.text()),
                'angle': float(self.angle_entry.text()),
                'proj_mat': self.material0_dropdown.currentText(),
                'type': self.target_type_dropdown.currentText(),
                'bumper_AD': float(self.bumperAD_entry.text()),
                'wall_mat': self.material1_dropdown.currentText(),
                'wall_thick': float(self.thickness1_entry.text()) if self.thickness1_entry.text() != "" else 0,
                'wall_density': float(self.density1_entry.text()) if self.density1_entry.text() != "" else 0,
                'wall_AD': float(self.wallAD_entry.text()) if self.wallAD_entry.text() != "" else 0,       
                'wall_yield': float(self.yield1_entry.text())*0.145038 if self.yield1_entry.text() != "" else 0,  # convert MPa to ksi    
                'standoff': float(self.standoff_entry.text()),
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
            if self.target_type_dropdown.currentText() == "Nextel rear wall":
                df_plot['dc_BLE'] = df_plot.apply(multishockNextel_performance,axis=1)
            elif self.target_type_dropdown.currentText() == "Kevlar rear wall":
                df_plot['dc_BLE'] = df_plot.apply(multishockKevlar_performance,axis=1)
            elif self.target_type_dropdown.currentText() == "Aluminium rear wall":
                df_plot['dc_BLE'] = df_plot.apply(multishockAl_performance,axis=1)
            elif self.target_type_dropdown.currentText() == "Hybrid shield":
                df_plot['dc_BLE'] = df_plot.apply(multishockHybrid_performance,axis=1)
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