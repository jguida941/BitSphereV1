import os
os.environ['QT_API'] = 'pyside6'
import sys
import numpy as np
import matplotlib

matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from PySide6.QtCore import Qt, QTimer

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QComboBox, QCheckBox
)

# VisualizationWorker class for threaded visualization computation
from PySide6.QtCore import QThread, Signal

class VisualizationWorker(QThread):
    # Signal: (power_set_positions, binary_positions, n, current_index, show_labels, show_connections)
    updated = Signal(list, list, int, int, bool, bool)

    def __init__(self, base_set, current_index, show_labels, show_connections):
        super().__init__()
        self.base_set = base_set
        self.current_index = current_index
        self.show_labels = show_labels
        self.show_connections = show_connections

    def run(self):
        n = len(self.base_set)
        power_set_positions = []
        binary_positions = []
        for i in range(2 ** n):
            # Allow early exit if interrupted
            if self.isInterruptionRequested():
                return

            theta = (i / (2 ** n)) * 2 * np.pi
            phi = np.pi / 3
            x = np.sin(phi) * np.cos(theta)
            y = np.sin(phi) * np.sin(theta)
            z = np.cos(phi)
            power_set_positions.append((x, y, z))

            phi2 = np.pi - phi
            x2 = np.sin(phi2) * np.cos(theta)
            y2 = np.sin(phi2) * np.sin(theta)
            z2 = np.cos(phi2)
            binary_positions.append((x2, y2, z2))

        # Check one more time before emitting
        if self.isInterruptionRequested():
            return

        self.updated.emit(
            power_set_positions,
            binary_positions,
            n,
            self.current_index,
            self.show_labels,
            self.show_connections
        )


class PowerSetBijectionVisualization(QMainWindow):
    def __init__(self):
        super().__init__()
        # Declare instance attributes to satisfy type checker
        self.size_spinner = None
        self.elements_input = None
        self.speed_combo = None
        self.animation_button = None
        self.show_labels_checkbox = None
        self.show_connections_checkbox = None
        self.power_set_table = None
        self.canvas = None
        self.ax = None
        self.current_subset_label = None
        self.current_binary_label = None
        self.current_decimal_label = None
        self.worker = None

        self.setWindowTitle("Power Set Bijection Visualization")
        self.setMinimumSize(1200, 800)

        # Data model
        self.base_set = ["x₁", "x₂", "x₃"]
        self.set_size = 3
        self.selected_subset = []
        self.current_binary = "000"
        self.animation_speed = 1000  # milliseconds
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.next_animation_step)
        self.animation_index = 0
        self.animation_running = False

        # Create UI
        self.init_ui()

        # Update visualization
        self.update_power_set()
        self.update_3d_visualization()

    def init_ui(self):
        # Main layout
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # Left panel (controls and table)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Controls
        controls_box = QWidget()
        controls_layout = QVBoxLayout(controls_box)

        # Set size control
        size_layout = QHBoxLayout()
        size_label = QLabel("Set Size:")
        self.size_spinner = QSpinBox()
        self.size_spinner.setRange(1, 6)  # Limit to 6 for performance and visual clarity
        self.size_spinner.setValue(self.set_size)
        self.size_spinner.valueChanged.connect(self.set_size_changed)
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.size_spinner)

        # Custom set elements
        elements_layout = QHBoxLayout()
        elements_label = QLabel("Set Elements (comma-separated):")
        self.elements_input = QLineEdit("x₁, x₂, x₃")
        self.elements_input.setPlaceholderText("e.g., a, b, c")
        self.elements_input.textChanged.connect(self.elements_changed)
        elements_layout.addWidget(elements_label)
        elements_layout.addWidget(self.elements_input)

        # Animation controls
        animation_layout = QHBoxLayout()
        self.animation_button = QPushButton("Start Animation")
        self.animation_button.clicked.connect(self.toggle_animation)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["Slow", "Medium", "Fast"])
        self.speed_combo.setCurrentIndex(1)
        self.speed_combo.currentIndexChanged.connect(self.speed_changed)
        animation_layout.addWidget(QLabel("Animation Speed:"))
        animation_layout.addWidget(self.speed_combo)
        animation_layout.addWidget(self.animation_button)

        # Visualization options
        viz_options_layout = QHBoxLayout()
        self.show_labels_checkbox = QCheckBox("Show Labels")
        self.show_labels_checkbox.setChecked(True)
        self.show_labels_checkbox.stateChanged.connect(self.update_3d_visualization)
        self.show_connections_checkbox = QCheckBox("Show Connections")
        self.show_connections_checkbox.setChecked(True)
        self.show_connections_checkbox.stateChanged.connect(self.update_3d_visualization)
        viz_options_layout.addWidget(self.show_labels_checkbox)
        viz_options_layout.addWidget(self.show_connections_checkbox)

        # Add all control layouts
        controls_layout.addLayout(size_layout)
        controls_layout.addLayout(elements_layout)
        controls_layout.addLayout(animation_layout)
        controls_layout.addLayout(viz_options_layout)

        # Theory and explanation
        theory_label = QLabel(
            "<h3>Bijection between Power Sets and Binary Strings</h3>"
            "<p>For a set X = {x₁, x₂, ..., xₙ}, the power set 2<sup>X</sup> contains all possible subsets of X.</p>"
            "<p>The bijection f: 2<sup>X</sup> → {0,1}<sup>n</sup> maps each subset Y ⊆ X to a binary string where:</p>"
            "<p>• The i-th bit is 1 if xᵢ ∈ Y, otherwise 0</p>"
            "<p>• Formally: f(Y) = y₁y₂...yₙ where yᵢ = 1 if xᵢ ∈ Y, otherwise yᵢ = 0</p>"
            "<p>The inverse function f<sup>-1</sup>: {0,1}<sup>n</sup> → 2<sup>X</sup> maps each binary string back to a subset.</p>"
            "<p>For every Y ⊆ X and every y ∈ {0,1}<sup>n</sup>, f(Y) = y ↔ f<sup>-1</sup>(y) = Y</p>"
        )
        theory_label.setWordWrap(True)

        # Power set table
        self.power_set_table = QTableWidget()
        self.power_set_table.setColumnCount(3)
        self.power_set_table.setHorizontalHeaderLabels(["Subset", "Binary String", "Decimal"])
        self.power_set_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.power_set_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.power_set_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.power_set_table.selectionModel().selectionChanged.connect(self.table_selection_changed)

        # Add widgets to left panel
        left_layout.addWidget(controls_box)
        left_layout.addWidget(theory_label)
        left_layout.addWidget(QLabel("<h3>Power Set to Binary String Mapping</h3>"))
        left_layout.addWidget(self.power_set_table)

        # Right panel (3D visualization)
        self.canvas = FigureCanvas(Figure(figsize=(8, 8)))
        self.ax = self.canvas.figure.add_subplot(111, projection='3d')
        # Enable point picking on the 3D canvas
        self.canvas.mpl_connect('pick_event', self.on_pick)

        # Current selection display
        selection_widget = QWidget()
        selection_layout = QVBoxLayout(selection_widget)

        selection_title = QLabel("<h3>Current Selection</h3>")
        self.current_subset_label = QLabel("Subset: ∅")
        self.current_binary_label = QLabel("Binary: 000")
        self.current_decimal_label = QLabel("Decimal: 0")

        selection_layout.addWidget(selection_title)
        selection_layout.addWidget(self.current_subset_label)
        selection_layout.addWidget(self.current_binary_label)
        selection_layout.addWidget(self.current_decimal_label)

        # Combine right panel widgets
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(selection_widget)
        right_layout.addWidget(self.canvas)

        # Add panels to main layout with splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])
        main_layout.addWidget(splitter)

        # Set main widget
        self.setCentralWidget(main_widget)

    def set_size_changed(self, value):
        self.set_size = value
        # Update base set with proper subscripts
        subscripts = ["₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈"]
        self.base_set = [f"x{subscripts[i]}" for i in range(min(value, 8))]
        self.elements_input.setText(", ".join(self.base_set))
        self.selected_subset = []
        self.current_binary = "0" * value
        self.update_power_set()
        self.update_3d_visualization()

    def elements_changed(self, text):
        elements = [e.strip() for e in text.split(",") if e.strip()]
        if len(elements) > 0:
            self.base_set = elements[:min(len(elements), 6)]  # Limit to 6 elements
            self.set_size = len(self.base_set)
            self.size_spinner.setValue(self.set_size)
            self.selected_subset = []
            self.current_binary = "0" * self.set_size
            self.update_power_set()
            self.update_3d_visualization()

    def update_power_set(self):
        # Generate all possible subsets and their binary representations
        power_set = []
        n = len(self.base_set)

        for i in range(2 ** n):
            # Convert i to binary string with leading zeros
            binary = format(i, f'0{n}b')

            # Create the subset based on the binary string
            subset = [self.base_set[j] for j in range(n) if binary[j] == '1']

            # Format the subset as a string
            if len(subset) == 0:
                subset_str = "∅"
            else:
                subset_str = "{" + ", ".join(subset) + "}"

            power_set.append((subset, subset_str, binary, i))

        # Update the table
        self.power_set_table.setRowCount(len(power_set))
        for row, (subset, subset_str, binary, decimal) in enumerate(power_set):
            self.power_set_table.setItem(row, 0, QTableWidgetItem(subset_str))
            self.power_set_table.setItem(row, 1, QTableWidgetItem(binary))
            self.power_set_table.setItem(row, 2, QTableWidgetItem(str(decimal)))

        # Highlight the current selection
        for row in range(self.power_set_table.rowCount()):
            binary_item = self.power_set_table.item(row, 1)
            if binary_item and binary_item.text() == self.current_binary:
                self.power_set_table.selectRow(row)
                break

    def table_selection_changed(self, selected, _deselected) -> None:
        indices = selected.indexes()
        if indices:
            row = indices[0].row()
            subset_str = self.power_set_table.item(row, 0).text()
            binary_str = self.power_set_table.item(row, 1).text()
            decimal_val = self.power_set_table.item(row, 2).text()

            # Update current selection
            if subset_str == "∅":
                self.selected_subset = []
            else:
                # Remove braces and split by comma
                subset_content = subset_str[1:-1].strip()
                if subset_content:
                    self.selected_subset = [item.strip() for item in subset_content.split(',')]
                else:
                    self.selected_subset = []

            self.current_binary = binary_str

            # Update labels
            self.current_subset_label.setText(f"Subset: {subset_str}")
            self.current_binary_label.setText(f"Binary: {binary_str}")
            self.current_decimal_label.setText(f"Decimal: {decimal_val}")

            # Update 3D visualization highlighting
            self.update_3d_visualization()

    def update_3d_visualization(self) -> None:
        # Stop previous worker if it's still running
        if getattr(self, 'worker', None) is not None and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        # Determine which index is selected and which flags are checked
        current_index = int(self.current_binary, 2) if self.current_binary else 0
        show_labels = self.show_labels_checkbox.isChecked()
        show_connections = self.show_connections_checkbox.isChecked()

        # Launch a worker thread to compute positions
        self.worker = VisualizationWorker(
            self.base_set,
            current_index,
            show_labels,
            show_connections
        )
        # When worker finishes, call draw_visualization on the main thread
        self.worker.updated.connect(self.draw_visualization)
        self.worker.start()

    def draw_visualization(self, power_set_positions, binary_positions, n, current_index, show_labels, show_connections) -> None:
        # Clear any previous plot
        self.ax.clear()

        # Configure axes
        self.ax.set_xlim([-1.5, 1.5])
        self.ax.set_ylim([-1.5, 1.5])
        self.ax.set_zlim([-1.5, 1.5])
        self.ax.set_xlabel('X')
        self.ax.set_ylabel('Y')
        self.ax.set_zlabel('Z')
        self.ax.set_title('Power Set to Binary String Bijection')

        # Plot each power-set node on the sphere
        for i, (x, y, z) in enumerate(power_set_positions):
            binary = format(i, f'0{n}b')
            subset = [self.base_set[j] for j in range(n) if binary[j] == '1']
            subset_str = "∅" if not subset else "{" + ", ".join(subset) + "}"

            if i == current_index:
                color, size = 'red', 100
            else:
                color, size = 'blue', 50

            self.ax.scatter(x, y, z, color=color, s=size, picker=5)
            if show_labels:
                self.ax.text(x * 1.1, y * 1.1, z * 1.1, subset_str, color=color, fontsize=8)

        # Plot each binary-string node on the opposite hemisphere
        for i, (x2, y2, z2) in enumerate(binary_positions):
            binary = format(i, f'0{n}b')
            if i == current_index:
                color, size = 'red', 100
            else:
                color, size = 'green', 50

            self.ax.scatter(x2, y2, z2, color=color, s=size, picker=5)
            if show_labels:
                self.ax.text(x2 * 1.1, y2 * 1.1, z2 * 1.1, binary, color=color, fontsize=8)

        # Draw connecting lines if requested
        if show_connections:
            for i in range(2 ** n):
                x1, y1, z1 = power_set_positions[i]
                x2, y2, z2 = binary_positions[i]
                if i == current_index:
                    color, linewidth = 'red', 2
                else:
                    color, linewidth = 'gray', 0.5
                self.ax.plot([x1, x2], [y1, y2], [z1, z2], color=color, linewidth=linewidth, alpha=0.5)

        # Draw the base set label at top
        self.ax.text(0, 0, 1.8, f"Base Set X = {{{', '.join(self.base_set)}}}", fontsize=10, ha='center', va='center')

        # Draw the formal definition at bottom
        formal_def = f"f: 2^X → {{0,1}}^{n} maps Y ⊆ X to binary string y₁y₂...y_{n}"
        self.ax.text(0, 0, -1.8, formal_def, fontsize=10, ha='center', va='center')

        # Finally redraw the canvas
        self.canvas.draw()

    def on_pick(self, event: object) -> None:
        # When a scatter point is clicked, update the table selection
        if not event.artist:
            return
        ind = event.ind[0] if isinstance(event.ind, (list, tuple)) else event.ind
        n = len(self.base_set)
        binary = format(ind, f'0{n}b')
        self.current_binary = binary
        # Find and select the corresponding row in the table
        for row in range(self.power_set_table.rowCount()):
            if self.power_set_table.item(row, 1).text() == binary:
                self.power_set_table.selectRow(row)
                break
        # Trigger a redraw via threaded mechanism
        self.update_3d_visualization()

    def toggle_animation(self):
        if self.animation_running:
            self.animation_timer.stop()
            self.animation_running = False
            self.animation_button.setText("Start Animation")
        else:
            self.animation_index = 0
            self.animation_timer.start(self.animation_speed)
            self.animation_running = True
            self.animation_button.setText("Stop Animation")

    def next_animation_step(self):
        # Select the next row in the table
        n = 2 ** len(self.base_set)
        next_index = (self.animation_index + 1) % n
        self.animation_index = next_index
        self.power_set_table.selectRow(next_index)

    def speed_changed(self, index):
        speeds = [2000, 1000, 500]  # Slow, Medium, Fast in milliseconds
        self.animation_speed = speeds[index]
        if self.animation_running:
            self.animation_timer.stop()
            self.animation_timer.start(self.animation_speed)

    def export_to_csv(self) -> None:
        # Implementation of export_to_csv would be here
        pass

    def closeEvent(self, event) -> None:
        # Stop worker thread if running
        if getattr(self, 'worker', None) is not None and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        # Stop animation timer if running
        if self.animation_running:
            self.animation_timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PowerSetBijectionVisualization()
    window.show()
    sys.exit(app.exec())