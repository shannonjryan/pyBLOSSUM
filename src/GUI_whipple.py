from PyQt5.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox, QLineEdit, QGroupBox, QPushButton, QMessageBox, QCheckBox, QFrame, QListWidget, QAbstractItemView
from PyQt5.QtCore import Qt
from functools import cached_property
import sys
import os
# Make the same package imports available when this file is run directly.
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not __package__:
    sys.path.insert(0, root_dir)

from BLEs.results_utils import create_run_directory, write_config_csv
from src.gui_support import material_properties, run_standalone, warm_analysis_libraries


class PlotWindow(QDialog):
    def __init__(self, parent=None):
        super(PlotWindow, self).__init__(parent)

        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        from matplotlib.figure import Figure

        ## Create a Figure and a FigureCanvas
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)

        ## Create a navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)

        ## Set a layout for the window
        self.layout = QVBoxLayout(self)

        ## Add the toolbar and the canvas to the layout
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas)

        ## Set the layout for the window
        self.setLayout(self.layout)

## ------------------------------------------------- ##
# Define the main GUI window
## ------------------------------------------------- ##
class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.materials = material_properties(root_dir)
        self.initUI()

    @cached_property
    def packages(self):
        packages = warm_analysis_libraries().result()
        from BLEs.BLE_JSCwhipple_mod import modJSCwhipple_curve
        from BLEs.BLE_JSCwhipple import JSCwhipple_curve
        from BLEs.BLE_reimerdeswhipple import reimerdes_curve
        from BLEs.BLE_NNOwhipple import NNO_curve
        from BLEs.BLE_modNNOwhipple import modNNO_curve

        return {
            **packages,
            'modJSCwhipple_curve': modJSCwhipple_curve,
            'JSCwhipple_curve': JSCwhipple_curve,
            'reimerdes_curve': reimerdes_curve,
            'NNO_curve': NNO_curve,
            'modNNO_curve': modNNO_curve,
        }

    def initUI(self):
        self.layout = QVBoxLayout(self)
        widget_width = 120
        self.setWindowTitle("Whipple shield")

        ## Define the list of materials
        self.AlMatList = list([
            "AA99.9%",
            "AA1100-O",
            "AA2017-T4",
            "AA2024-T3",
            "AA2024-T351",
            "AA2024-T4",
            "AA2219-T87",
            "AA3003-H12",
            "AA3003-H14",
            "AA6061-T6",
            "AA6061-T651",
            "AA7075-T6"])

        ## Define the initial materials
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
        self.density0_entry.setText("2.8")
        self.frame1_layout.addWidget(self.density0_entry, 1, 1)

        ## ------------------------------------------------- ##
        # Second frame (bumper plate)
        ## ------------------------------------------------- ##
        self.frame2 = QGroupBox("Bumper plate", self)
        self.frame2.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame2)

        self.frame2_layout = QGridLayout(self.frame2)

        self.material1_label = QLabel("Material:", self.frame2)
        self.frame2_layout.addWidget(self.material1_label, 0, 0)
        self.material1_dropdown = QComboBox(self)
        self.material1_dropdown.setFixedWidth(widget_width)
        self.material1_dropdown.addItems(self.AlMatList)
        self.material1_dropdown.setCurrentText(self.initial_bumper_mat) 
        self.material1_dropdown.currentIndexChanged.connect(self.on_material1_selected)
        self.frame2_layout.addWidget(self.material1_dropdown, 0, 1)

        self.thickness1_label = QLabel("Thickness (cm):", self)
        self.frame2_layout.addWidget(self.thickness1_label, 1, 0)
        self.thickness1_entry = QLineEdit(self)
        self.thickness1_entry.setFixedWidth(widget_width)
        self.frame2_layout.addWidget(self.thickness1_entry, 1, 1)

        self.density1_label = QLabel("Density (g/cm³):", self)
        self.frame2_layout.addWidget(self.density1_label, 2, 0)
        self.density1_entry = QLineEdit(self)
        self.density1_entry.setFixedWidth(widget_width)
        self.density1_entry.setText("2.7")
        self.frame2_layout.addWidget(self.density1_entry, 2, 1)

        self.standoff_label = QLabel("Standoff (cm):", self)
        self.frame2_layout.addWidget(self.standoff_label, 3, 0)
        self.standoff_entry = QLineEdit(self)
        self.standoff_entry.setFixedWidth(widget_width)
        self.frame2_layout.addWidget(self.standoff_entry, 3, 1)        

        ## ------------------------------------------------- ##
        # Third frame (rear wall)
        ## ------------------------------------------------- ##
        self.frame3 = QGroupBox("Rear wall", self)
        self.frame3.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame3)

        self.frame3_layout = QGridLayout(self.frame3)

        self.material2_label = QLabel("Material:", self.frame3)
        self.frame3_layout.addWidget(self.material2_label, 0, 0)
        self.material2_dropdown = QComboBox(self)
        self.material2_dropdown.setFixedWidth(widget_width)        
        self.material2_dropdown.addItems(self.AlMatList)
        self.material2_dropdown.setCurrentText(self.initial_wall_mat) 
        self.material2_dropdown.currentIndexChanged.connect(self.on_material2_selected)
        self.frame3_layout.addWidget(self.material2_dropdown, 0, 1)

        self.thickness2_label = QLabel("Thickness (cm):", self)
        self.frame3_layout.addWidget(self.thickness2_label, 1, 0)
        self.thickness2_entry = QLineEdit(self)
        self.thickness2_entry.setFixedWidth(widget_width)        
        self.frame3_layout.addWidget(self.thickness2_entry, 1, 1)

        self.density2_label = QLabel("Density (g/cm³):", self)
        self.frame3_layout.addWidget(self.density2_label, 2, 0)
        self.density2_entry = QLineEdit(self)
        self.density2_entry.setFixedWidth(widget_width)
        self.density2_entry.setText("2.7")
        self.frame3_layout.addWidget(self.density2_entry, 2, 1)

        self.yield2_label = QLabel("Yield strength (MPa):", self)
        self.frame3_layout.addWidget(self.yield2_label, 3, 0)
        self.yield2_entry = QLineEdit(self)
        self.yield2_entry.setFixedWidth(widget_width)        
        self.yield2_entry.setText("276")
        self.frame3_layout.addWidget(self.yield2_entry, 3, 1)

        ## ------------------------------------------------- ##
        # Fourth frame (MLI)
        ## ------------------------------------------------- ##
        self.frame4 = QGroupBox("MLI", self)
        self.frame4.setStyleSheet("QGroupBox { font: bold 12px; }")
        self.layout.addWidget(self.frame4)

        self.frame4_layout = QGridLayout(self.frame4)

        self.mli_type_label = QLabel("MLI type:", self)
        self.frame4_layout.addWidget(self.mli_type_label, 0, 0)
        self.mli_type_dropdown = QComboBox(self)
        self.mli_type_dropdown.setFixedWidth(widget_width)
        self.mli_type_dropdown.addItems(["None","External","Internal"])
        self.initial_mli_type = "None"
        self.mli_type_dropdown.setCurrentText(self.initial_mli_type)
        self.frame4_layout.addWidget(self.mli_type_dropdown, 0, 1)
        self.mli_type_dropdown.currentTextChanged.connect(self.on_mli_type_changed)

        self.MLIad_label = QLabel("MLI AD (g/cm²):", self)
        self.frame4_layout.addWidget(self.MLIad_label, 1, 0)
        self.MLIad_entry = QLineEdit(self)
        self.MLIad_entry.setFixedWidth(widget_width)             
        self.frame4_layout.addWidget(self.MLIad_entry, 1, 1)
        self.MLIad_entry.setEnabled(False)

        self.MLIs_label = QLabel("MLI standoff (cm):", self)
        self.frame4_layout.addWidget(self.MLIs_label, 2, 0)
        self.MLIs_entry = QLineEdit(self)
        self.MLIs_entry.setFixedWidth(widget_width)             
        self.frame4_layout.addWidget(self.MLIs_entry, 2, 1)
        self.MLIs_entry.setEnabled(False)

        ## ------------------------------------------------- ##
        # Fifth frame - select ballistic limit equations
        ## ------------------------------------------------- ##
        self.frame5 = QFrame(self)
        self.frame5.setFrameShape(QFrame.StyledPanel)
        self.frame5.setFrameShadow(QFrame.Raised)

        self.frame5_layout = QVBoxLayout(self.frame5)

        self.list_label = QLabel("Ballistic limit equations", self.frame5)
        self.frame5_layout.addWidget(self.list_label)
        self.list_widget = QListWidget(self.frame5)
        self.list_widget.setSelectionMode(QAbstractItemView.MultiSelection)
        self.list_widget.addItems(["JSC Whipple (mod)", "New non-optimum (NNO)", "JSC Whipple", "Reimerdes-modified NNO", "Christiansen-modified NNO"])

        ## Set "JSC Whipple (mod)" on by default
        items = self.list_widget.findItems("JSC Whipple (mod)", Qt.MatchExactly)
        if items:
            self.list_widget.setCurrentItem(items[0])

        self.list_widget.setMinimumHeight(self.list_widget.count() * 20)
        self.frame5_layout.addWidget(self.list_widget)
        self.layout.addWidget(self.frame5)

        ## ------------------------------------------------- ##
        # Sixth frame - include experimental data in the plot
        ## ------------------------------------------------- ##
        self.frame6 = QFrame(self)
        self.frame6.setFrameShape(QFrame.StyledPanel)
        self.frame6.setFrameShadow(QFrame.Raised)

        self.frame6_layout = QVBoxLayout(self.frame6)

        self.plot_test_data_checkbox = QCheckBox("Include relevant test data in plot?", self.frame6)
        self.frame6_layout.addWidget(self.plot_test_data_checkbox)
        self.frame6_layout.addWidget(self.plot_test_data_checkbox)
        self.layout.addWidget(self.frame6)

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
        density = self.materials[selected_material]['density']
        self.density0_entry.setText(str(density))

    ## ------------------------------------------------- ##
    def on_material1_selected(self, index):
        selected_material = self.material1_dropdown.itemText(index)
        density = self.materials[selected_material]['density']
        self.density1_entry.setText(str(density))

    ## ------------------------------------------------- ##
    def on_material2_selected(self, index):
        selected_material = self.material2_dropdown.itemText(index)
        density2 = self.materials[selected_material]['density']
        yield2 = self.materials[selected_material]['yield']
        self.density2_entry.setText(str(density2))
        self.yield2_entry.setText(str(yield2))   

    ## ------------------------------------------------- ##
    def on_mli_type_changed(self, text):
        if text == "Internal":
            self.MLIad_entry.setEnabled(True)
            self.MLIs_entry.setEnabled(True)
        elif text == "External":
            self.MLIad_entry.setEnabled(True)
            self.MLIs_entry.setEnabled(False)
        else:
            self.MLIad_entry.setEnabled(False)
            self.MLIs_entry.setEnabled(False)

    ## ------------------------------------------------- ##
    def on_run_button_clicked(self):
        try:
            pd = self.packages['pd']
            color_line_style_cycler = self.packages['itertools'].cycle(self.packages['color_line_style_pairs'])
            ## Check if any of the text boxes are empty
            if not all([self.angle_entry.text(), self.density0_entry.text(),
                        self.thickness1_entry.text(), self.density1_entry.text(), self.standoff_entry.text(),
                        self.thickness2_entry.text(), self.density2_entry.text(), self.yield2_entry.text()]):
                raise ValueError("All fields must be filled out.")
            np = self.packages['np']
            mli_mode = self.mli_type_dropdown.currentText()
            mli_ad = self.MLIad_entry.text().strip() if mli_mode in ("External", "Internal") else "0"
            mli_standoff = self.MLIs_entry.text().strip() if mli_mode == "Internal" else "0"
            if not mli_ad or not mli_standoff:
                raise ValueError("Fill out the MLI fields for the selected MLI type.")
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
                'AD_MLI': float(mli_ad),  # units = g/cm2
                'S_MLI': float(mli_standoff),  # units = cm
            }
            positive_fields = {
                'proj_density': 'Projectile density',
                'bumper_thick': 'Bumper thickness',
                'bumper_density': 'Bumper density',
                'standoff': 'Shield standoff',
                'wall_thick': 'Rear wall thickness',
                'wall_density': 'Rear wall density',
                'wall_yield': 'Rear wall yield strength',
            }
            if mli_mode in ("External", "Internal"):
                positive_fields['AD_MLI'] = 'MLI areal density'
            if mli_mode == "Internal":
                positive_fields['S_MLI'] = 'MLI standoff'
            for field, label in positive_fields.items():
                if not np.isfinite(data[field]) or data[field] <= 0:
                    raise ValueError(f"{label} must be finite and greater than zero.")
            if not 0 <= data['angle'] <= 90:
                raise ValueError("Impact angle must be finite and between 0 and 90 degrees.")

            items = self.list_widget.selectedItems()
            if not items:
                raise ValueError("Select at least one ballistic limit equation.")
            models = {
                "New non-optimum (NNO)": ('NNO_curve', 'dc_NNO', 'New non-optimum (NNO)'),
                "Christiansen-modified NNO": ('modNNO_curve', 'dc_modNNO', 'Christiansen-modified NNO'),
                "Reimerdes-modified NNO": ('reimerdes_curve', 'dc_reimerdes', 'Reimerdes'),
                "JSC Whipple": ('JSCwhipple_curve', 'dc_JSCwhipple', 'JSC Whipple'),
                "JSC Whipple (mod)": ('modJSCwhipple_curve', 'dc_modJSCwhipple', 'JSC Whipple (mod)'),
            }
            velocities = np.linspace(0.1, 15, 150)  # units = km/s
            df_results = pd.DataFrame({'velocity': velocities})
            plot_curves = []
            for item in items:
                function, column, label = models[item.text()]
                diameters = np.asarray(self.packages[function](data, velocities))
                if (diameters.shape != velocities.shape
                        or not np.issubdtype(diameters.dtype, np.number) or not np.isrealobj(diameters)
                        or not np.isfinite(diameters).all() or np.any(diameters <= 0)):
                    raise ValueError(f"{label} returned an invalid diameter curve.")
                df_results[column] = diameters
                plot_curves.append((label, diameters))
            df_config = pd.DataFrame([data])

            ## Create a plot window
            self.plot_window = PlotWindow()

            ## Create a plot
            ax = self.plot_window.figure.add_subplot(111)

            pltmax = max(diameters[len(velocities)//2] for _, diameters in plot_curves)
            for label, diameters in plot_curves:
                color, line_style = next(color_line_style_cycler)
                ax.plot(velocities, diameters, color=color, linestyle=line_style, label=label)

            ## If the 'include test data' checkbox is ticked, plot the test data
            if self.plot_test_data_checkbox.isChecked():
                ## Load the test data
                filename = 'database_whipple_pyBLOSSUM.csv'
                df_test = pd.read_csv(os.path.join(root_dir,'data',filename),skiprows=[1])
                
                ## Filter the test data based on the selected values
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
            save_plot = self.save_plot_checkbox.isChecked()
            save_data = self.save_data_checkbox.isChecked()
            if save_plot or save_data:
                results_dir, now_str = create_run_directory(root_dir)

            if save_plot:
                self.plot_window.figure.savefig(results_dir / f"plot_{now_str}.png")

            ## If the save_data_checkbox is checked, save the velocity and critical diameter data, as well as config data
            if save_data:
                df_config['wall_yield'] = df_config['wall_yield']/0.145038  # convert ksi to MPa

                ## Write the output data to a CSV file
                df_results.to_csv(results_dir / f"blc_data_{now_str}.csv", index=False)
                write_config_csv(df_config, results_dir / f"config_data_{now_str}.csv")

                if self.plot_test_data_checkbox.isChecked():
                    # write the relevant test data to file
                    df_filtered_test_data.to_csv(results_dir / f"test_data_{now_str}.csv", index=False)

        except (ImportError, ValueError, OSError) as e:
            QMessageBox.critical(self, "Error", str(e))

## ------------------------------------------------- ##
# Run the application
## ------------------------------------------------- ##            
if __name__ == "__main__":
    sys.exit(run_standalone(MyApp))
