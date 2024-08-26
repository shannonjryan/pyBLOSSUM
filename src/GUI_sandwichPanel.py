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
        from BLE_SRL import SRL_double_performance
        from BLE_foamSP import foamSP_performance

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
            'SRL_double_performance': SRL_double_performance,
            'foamSP_performance': foamSP_performance
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
        self.setWindowTitle("Sandwich panel")

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
        self.initial_bumper_mat = "AA6061-T651"
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

        self.density0_label = QLabel("Density (g/cm³):", self)
        self.frame1_layout.addWidget(self.density0_label, 1, 0)
        self.density0_entry = QLineEdit(self)
        self.density0_entry.setFixedWidth(widget_width)
        # self.density0_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_proj_mat, 'density'].values[0]))
        self.density0_entry.setText("2.8")
        self.frame1_layout.addWidget(self.density0_entry, 1, 1)

        ## ------------------------------------------------- ##
        # Second frame - select core type
        ## ------------------------------------------------- ##
        self.frame2 = QFrame(self)
        self.frame2.setFrameShape(QFrame.StyledPanel)
        self.frame2.setFrameShadow(QFrame.Raised)

        self.frame2_layout = QGridLayout(self.frame2)

        self.core_type_label = QLabel("Core type:", self)
        self.frame2_layout.addWidget(self.core_type_label, 0, 0)
        self.core_type_dropdown = QComboBox(self)
        self.core_type_dropdown.setFixedWidth(widget_width)
        self.core_type_dropdown.addItems(["Honeycomb", "Foam"])
        self.frame2_layout.addWidget(self.core_type_dropdown, 0, 1)
        self.layout.addWidget(self.frame2)
        self.core_type_dropdown.currentTextChanged.connect(self.on_core_type_changed)

        ## ------------------------------------------------- ##
        # Third frame (sandwich panel)
        ## ------------------------------------------------- ##
        self.frame3 = QGroupBox("Sandwich panel", self)
        self.frame3.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame3)

        self.frame3_layout = QGridLayout(self.frame3)

        self.material1_label = QLabel("Front facesheet material:", self.frame3)
        self.frame3_layout.addWidget(self.material1_label, 0, 0)
        self.material1_dropdown = QComboBox(self)
        self.material1_dropdown.setFixedWidth(widget_width)        
        self.material1_dropdown.addItems(self.AlMatList + ["CFRP", "Other"])
        self.material1_dropdown.setCurrentText(self.initial_bumper_mat) 
        self.material1_dropdown.currentIndexChanged.connect(self.on_material1_selected)
        self.frame3_layout.addWidget(self.material1_dropdown, 0, 1)

        self.thickness1_label = QLabel("Front facesheet thickness (cm):", self)
        self.frame3_layout.addWidget(self.thickness1_label, 1, 0)
        self.thickness1_entry = QLineEdit(self)
        self.thickness1_entry.setFixedWidth(widget_width)        
        self.frame3_layout.addWidget(self.thickness1_entry, 1, 1)

        self.density1_label = QLabel("Front facesheet density (g/cm³):", self)
        self.frame3_layout.addWidget(self.density1_label, 2, 0)
        self.density1_entry = QLineEdit(self)
        self.density1_entry.setFixedWidth(widget_width)
        # self.density1_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_bumper_mat, 'density'].values[0]))
        self.density1_entry.setText("2.7")
        self.frame3_layout.addWidget(self.density1_entry, 2, 1)

        self.standoff_label = QLabel("Core thickness (cm):", self)
        self.frame3_layout.addWidget(self.standoff_label, 3, 0)
        self.standoff_entry = QLineEdit(self)
        self.standoff_entry.setFixedWidth(widget_width)        
        self.frame3_layout.addWidget(self.standoff_entry, 3, 1)   

        self.material2_label = QLabel("Rear facesheet material:", self.frame3)
        self.frame3_layout.addWidget(self.material2_label, 4, 0)
        self.material2_dropdown = QComboBox(self)
        self.material2_dropdown.setFixedWidth(widget_width)        
        self.material2_dropdown.addItems(self.AlMatList + ["CFRP", "Other"])
        self.material2_dropdown.setCurrentText(self.initial_wall_mat) 
        self.material2_dropdown.currentIndexChanged.connect(self.on_material2_selected)
        self.frame3_layout.addWidget(self.material2_dropdown, 4, 1)

        self.thickness2_label = QLabel("Rear facesheet thickness (cm):", self)
        self.frame3_layout.addWidget(self.thickness2_label, 5, 0)
        self.thickness2_entry = QLineEdit(self)
        self.thickness2_entry.setFixedWidth(widget_width)        
        self.frame3_layout.addWidget(self.thickness2_entry, 5, 1)

        self.density2_label = QLabel("Rear facesheet density (g/cm³):", self)
        self.frame3_layout.addWidget(self.density2_label, 6, 0)
        self.density2_entry = QLineEdit(self)
        self.density2_entry.setFixedWidth(widget_width)
        # self.density2_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_wall_mat, 'density'].values[0]))
        self.density2_entry.setText("2.7")
        self.frame3_layout.addWidget(self.density2_entry, 6, 1)

        self.yield2_label = QLabel("Rear facesheet yield strength (MPa):", self)
        self.frame3_layout.addWidget(self.yield2_label, 7, 0)
        self.yield2_entry = QLineEdit(self)
        self.yield2_entry.setFixedWidth(widget_width)        
        # self.yield2_entry.setText(str(df_materials.loc[df_materials['mat'] == self.initial_wall_mat, 'yield'].values[0]))
        self.yield2_entry.setText("276")
        self.frame3_layout.addWidget(self.yield2_entry, 7, 1)

        self.MLI_label = QLabel("MLI AD (g/cm²):", self)
        self.frame3_layout.addWidget(self.MLI_label, 8, 0)
        self.MLI_entry = QLineEdit(self)
        self.MLI_entry.setFixedWidth(widget_width)             
        self.frame3_layout.addWidget(self.MLI_entry, 8, 1)

        ## ------------------------------------------------- ##
        # Fourth frame (foam-specific entries)
        ## ------------------------------------------------- ##
        self.frame4 = QGroupBox("Foam-specific parameters", self)
        self.frame4.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame4)

        self.frame4_layout = QGridLayout(self.frame4)
        self.panel_mass_label = QLabel("Panel mass (g):", self)
        self.frame4_layout.addWidget(self.panel_mass_label, 1, 0)
        self.panel_mass_entry = QLineEdit(self)
        self.panel_mass_entry.setDisabled(True)
        self.panel_mass_entry.setFixedWidth(widget_width)        
        self.frame4_layout.addWidget(self.panel_mass_entry, 1, 1)           

        self.panel_AD_label = QLabel("Panel AD (g/cm<sup>2</sup>):", self)
        self.frame4_layout.addWidget(self.panel_AD_label, 2, 0)
        self.panel_AD_entry = QLineEdit(self)
        self.panel_AD_entry.setDisabled(True)
        self.panel_AD_entry.setFixedWidth(widget_width)        
        self.frame4_layout.addWidget(self.panel_AD_entry, 2, 1)

        self.foam_density_label = QLabel("Foam density (g/cm<sup>3</sup>):", self)
        self.frame4_layout.addWidget(self.foam_density_label, 3, 0)
        self.foam_density_entry = QLineEdit(self)
        self.foam_density_entry.setDisabled(True)
        self.foam_density_entry.setFixedWidth(widget_width)        
        self.frame4_layout.addWidget(self.foam_density_entry, 3, 1)            

        self.foam_AD_label = QLabel("Foam AD (g/cm<sup>2</sup>):", self)
        self.frame4_layout.addWidget(self.foam_AD_label, 4, 0)
        self.foam_AD_entry = QLineEdit(self)
        self.foam_AD_entry.setDisabled(True)
        self.foam_AD_entry.setFixedWidth(widget_width)        
        self.frame4_layout.addWidget(self.foam_AD_entry, 4, 1)     

        # Add a note below the boxes
        self.note_label = QLabel("NOTE: A value is needed for one of the four variables", self)
        self.note_label.setStyleSheet("font-size: 10px;")  # Set the font size to 10px
        self.frame4_layout.addWidget(self.note_label, 5, 0, 1, 2)  # Span the label across two columns             

        ## ------------------------------------------------- ##
        # Fifth frame - include experimental data in the plot
        ## ------------------------------------------------- ##
        self.frame5 = QFrame(self)
        self.frame5.setFrameShape(QFrame.StyledPanel)
        self.frame5.setFrameShadow(QFrame.Raised)

        self.frame5_layout = QVBoxLayout(self.frame5)

        self.plot_test_data_checkbox = QCheckBox("Include relevant test data in plot?", self.frame5)
        self.frame5_layout.addWidget(self.plot_test_data_checkbox)
        self.frame5_layout.addWidget(self.plot_test_data_checkbox)
        self.layout.addWidget(self.frame5)

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
    def on_material1_selected(self, index):
        selected_material = self.material1_dropdown.itemText(index)
        if selected_material != 'CFRP' and selected_material != 'Other':
            density1 = self.df_materials.loc[self.df_materials['mat'] == selected_material, 'density'].values[0]
            self.density1_entry.setText(str(density1))
        else:
            self.density1_entry.setText("")            

    ## ------------------------------------------------- ##
    def on_material2_selected(self, index):
        selected_material = self.material2_dropdown.itemText(index)
        if selected_material != 'CFRP' and selected_material != 'Other':
            density2 = self.df_materials.loc[self.df_materials['mat'] == selected_material, 'density'].values[0]
            yield2 = self.df_materials.loc[self.df_materials['mat'] == selected_material, 'yield'].values[0]
            self.density2_entry.setText(str(density2))
            self.yield2_entry.setEnabled(True)
            self.yield2_entry.setText(str(yield2))  
        else:
            self.density2_entry.setText("")
            self.yield2_entry.setText("410")  
            self.yield2_entry.setDisabled(True)

    ## ------------------------------------------------- ##
    def on_core_type_changed(self, text):
        if text == "Foam":
            self.panel_mass_entry.setEnabled(True)
            self.panel_AD_entry.setEnabled(True)
            self.foam_density_entry.setEnabled(True)
            self.foam_AD_entry.setEnabled(True)
        else:
            self.panel_mass_entry.setDisabled(True)
            self.panel_AD_entry.setDisabled(True)
            self.foam_density_entry.setDisabled(True)
            self.foam_AD_entry.setDisabled(True)

    ## ------------------------------------------------- ##
    def on_run_button_clicked(self):

        color_line_style_cycler = self.packages['itertools'].cycle(self.packages['color_line_style_pairs'])
        
        try:           
            # Check if any of the text boxes are empty
            if not all([self.angle_entry.text(), self.density0_entry.text(),self.thickness1_entry.text(), 
                        self.density1_entry.text(), self.standoff_entry.text(),self.thickness2_entry.text(),
                        self.density2_entry.text(),self.yield2_entry.text()]):

                raise ValueError("All fields must be filled out.")
            else:
                print("All fields filled.")     

            data = {
                'proj_mat': self.material0_dropdown.currentText(),
                'proj_density': float(self.density0_entry.text()),  # units = g/cm3
                'angle': float(self.angle_entry.text()),  # units = deg
                'bumper_mat': self.material1_dropdown.currentText(),
                'bumper_thick': float(self.thickness1_entry.text()),  # units = cm
                'bumper_density': float(self.density1_entry.text()),  # units = g/cm3            
                'standoff': float(self.standoff_entry.text()),  # units = cm
                'wall_mat': self.material2_dropdown.currentText(),
                'wall_thick': float(self.thickness2_entry.text()),  # units = cm
                'wall_density': float(self.density2_entry.text()),  # units = g/cm3
                'wall_yield': float(self.yield2_entry.text())*0.145038,  # convert MPa to ksi
                'AD_MLI': float(self.MLI_entry.text()) if self.MLI_entry.text != "" else 0  #  units = g/cm2
            }

            ## add additional core data when the analysis is for an open cell foam
            if self.core_type_dropdown.currentText() == "Foam":
                data['SP_mass'] = float(self.panel_mass_entry.text() or "0")
                data['SP_AD'] = float(self.panel_AD_entry.text() or "0")
                data['foam_density'] = float(self.foam_density_entry.text() or "0")
                data['foam_AD'] = float(self.foam_AD_entry.text() or "0")

            df = pd.DataFrame([data])
    
            # Get the current date and time
            now = self.packages['datetime'].now()
            now_str = now.strftime("%Y%m%d_%H%M%S")

            # Create a plot window
            self.plot_window = PlotWindow()

            # Create a plot
            ax = self.plot_window.figure.add_subplot(111)

            # Call the ballistic limit equation
            velocities = self.packages['np'].linspace(0.1, 15, 150)  # units = km/s
            df_plot = pd.DataFrame(self.packages['np'].repeat(df.values, len(velocities), axis=0), columns=df.columns)
            df_plot['velocity'] = velocities
            pltmax = 0
            df_config = df_plot.iloc[[0]].drop(columns=['velocity']) 
            df_results = df_plot[['velocity']].copy()
            color, line_style = next(color_line_style_cycler)
            if self.core_type_dropdown.currentText() == "Honeycomb":
                df_plot['dc_BLE'] = df_plot.apply(self.packages['SRL_double_performance'],axis=1)
            elif self.core_type_dropdown.currentText() == "Foam":
                df_plot['dc_BLE'] = df_plot.apply(self.packages['foamSP_performance'],axis=1)
            ax.plot(df_plot['velocity'],df_plot['dc_BLE'],color=color,linestyle=line_style,label='BLE')
            pltmax = max(pltmax, df_plot['dc_BLE'][len(velocities)/2])
            df_results.insert(len(df_results.columns), 'dc_BLE', df_plot['dc_BLE'])

            # If the 'include test data' checkbox is ticked, plot the test data
            if self.plot_test_data_checkbox.isChecked():
                # Load the test data
                if self.core_type_dropdown.currentText() == "Honeycomb":
                    filename = 'database_HCSP_pyBLOSSUM.csv'
                elif self.core_type_dropdown.currentText() == "Foam":
                    filename = 'database_foamSP_pyBLOSSUM.csv'                
                df_test = pd.read_csv(os.path.join(root_dir,'data',filename),skiprows=[1])
                
                # Filter the test data based on the selected values
                lower_bound = 0.95
                upper_bound = 1.05
                mask = ((df_test['bumper_mat'].str[:9] == self.material1_dropdown.currentText()[:9]) &  # allows for e.g., AA6061-T651 and AA6061-T6 to be handled as common materials
                        (df_test['bumper_thick'] >= lower_bound * float(self.thickness1_entry.text())) &
                        (df_test['bumper_thick'] <= upper_bound * float(self.thickness1_entry.text())) &
                        (df_test['standoff'] >= lower_bound * float(self.standoff_entry.text())) &
                        (df_test['standoff'] <= upper_bound * float(self.standoff_entry.text())) &
                        (df_test['wall_mat'].str[:9] == self.material2_dropdown.currentText()[:9]) &  # allows for e.g., AA6061-T651 and AA6061-T6 to be handled as common materials
                        (df_test['wall_thick'] >= lower_bound * float(self.thickness2_entry.text())) &
                        (df_test['wall_thick'] <= upper_bound * float(self.thickness2_entry.text())) &
                        (df_test['angle'] == float(self.angle_entry.text())))
                df_filtered_test_data = df_test[mask]
                df_NP = df_filtered_test_data[df_filtered_test_data['perforated_class'] == 0]
                df_P = df_filtered_test_data[df_filtered_test_data['perforated_class'] == 1]
                ax.scatter(df_NP['velocity'],df_NP['proj_diam'],edgecolors='black',facecolors='black',label='NP')
                ax.scatter(df_P['velocity'],df_P['proj_diam'],edgecolors='black',facecolors='white',label='P')

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

                if self.core_type_dropdown.currentText() == "Honeycomb":
                    df_config['type'] = 'Honeycomb'
                elif self.core_type_dropdown.currentText() == "Foam":
                    df_config['type'] = 'Foam'

                df_config['wall_yield'] = df_config['wall_yield']/0.145038  # convert ksi to MPa
                
                ## Write the output data to a CSV file
                df_results.to_csv(os.path.join(root_dir,"results",f"blc_data_{now_str}.csv"), index=False)     
                df_config.to_csv(os.path.join(root_dir,"results",f"config_data_{now_str}.csv"), index=False)    

                if self.plot_test_data_checkbox.isChecked():
                    ## write the relevant test data to file
                    df_filtered_test_data.to_csv(os.path.join(root_dir,"results",f"test_data_{now_str}.csv"), index=False)  

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