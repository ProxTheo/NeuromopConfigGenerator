import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QComboBox, QPushButton,
    QGridLayout, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, QSpinBox, QLineEdit
)
from PySide6.QtGui import QRegularExpressionValidator, QIcon, QPainter, QPen, QColor
from PySide6.QtCore import Qt, QRegularExpression, QRect
# ============================================================
# Unit names
# ============================================================

UNIT_NAMES = {
    0: "ADC/Coat",
    1: "Amplifier",
    2: "Stimulator",
    3: "Decoder/Stim Buffer",
}


# ============================================================
# Protocol schema
#
# Segments are defined MSB -> LSB.
#
# Segment types:
# - const : fixed bit value
# - uint  : integer field with width N
# - bool  : checkbox, 1 bit
# - reserved : fixed 0 bits, shown as informational label only
# ============================================================

PROTOCOL_SCHEMAS = {
    0: [
        {
            "name": "ADC Config",
            "fixed_task": 0,
            "config_segments": [
                {"type": "uint", "name": "ADC_Config", "bits": 8}
            ],
        },
        {
            "name": "Coating/Shorting",
            "fixed_task": 1,
            "config_segments": [
                {"type": "reserved", "bits": 8, "label": "Unused / don't care"}
            ],
        },
        {
            "name": "ADC Start",
            "fixed_task": 2,
            "config_segments": [
                {"type": "reserved", "bits": 8, "label": "Unused / don't care"}
            ],
        },
    ],

    1: [
        {
            "name": "2nd Stage Amplifier Config",
            "fixed_task": 0,
            "config_segments": [
                {"type": "reserved", "bits": 3, "label": "Upper bits unused"},
                {"type": "uint", "name": "Conf_2", "bits": 5},
            ],
        },
        {
            "name": "4th Stage Amplifier Config",
            "fixed_task": 1,
            "config_segments": [
                {"type": "reserved", "bits": 2, "label": "Upper bits unused"},
                {"type": "uint", "name": "Conf_34", "bits": 6},
            ],
        },
    ],

    2: [
        {
            "name": "LEFT_SIDE SR",
            "fixed_task": 0,
            "config_segments": [
                {
                    "type": "uint",
                    "name": "LEFT_SIDE_SR",
                    "bits": 8,
                    "reverse_bits": True
                },
            ],
        },
        {
            "name": "IV Selection & Stim Enable",
            "fixed_task": 1,
            "config_segments": [
                # bit[7] = V/I load flag
                {"type": "bool", "name": "Load_VI"},

                # bit[6:5] = V/I values
                {"type": "bool", "name": "V"},
                {"type": "bool", "name": "I"},

                # bit[4] = Stim_EN load flag
                {"type": "bool", "name": "Load_Stim_EN"},

                # bit[3:0] = Stim_EN value
                {
                    "type": "uint",
                    "name": "Stim_EN",
                    "bits": 4,
                    "reverse_bits": True
                },
            ],
        },

        {
            "name": "P_off",
            "fixed_task": 2,
            "config_segments": [
                # bit[7] = don't care / unused
                {"type": "reserved", "bits": 1, "label": "Unused / X"},

                # bit[6] = res load flag
                {"type": "bool", "name": "Load_res"},

                # bit[5:2] = P_off value
                {
                    "type": "uint",
                    "name": "P_off",
                    "bits": 4,
                    "reverse_bits": True
                },

                # bit[1] = P_off load flag
                {"type": "bool", "name": "Load_P_off"},

                # bit[0] = res value
                {"type": "bool", "name": "res"},
            ],
        },
        {
            "name": "Current Read & Gain",
            "fixed_task": 3,
            "config_segments": [
                {"type": "const", "bits": 1, "value": 1, "label": "Fixed 1"},
                {
                    "type": "uint",
                    "name": "Cur_read",
                    "bits": 2,
                    "reverse_bits": True
                },
                {"type": "bool", "name": "P_off_cread"},

                # Reordered to match new left_g_rec wiring
                {"type": "bool", "name": "g1"},
                {"type": "bool", "name": "g100"},
                {"type": "bool", "name": "g50"},
                {"type": "bool", "name": "g25"},
            ],
        },
    ],

    3: [
        {
            "name": "Decoder Enable Odd",
            "task_segments": [
                {"type": "const", "bits": 1, "value": 1, "label": "Fixed 1"},
                {"type": "uint", "name": "Decoder_Index", "bits": 2},
                {"type": "const", "bits": 1, "value": 0, "label": "Odd suffix 0"},
            ],
            "config_segments": [
                {"type": "bool", "name": "Block 15"},
                {"type": "bool", "name": "Block 13"},
                {"type": "bool", "name": "Block 11"},
                {"type": "bool", "name": "Block 9"},
                {"type": "bool", "name": "Block 7"},
                {"type": "bool", "name": "Block 5"},
                {"type": "bool", "name": "Block 3"},
                {"type": "bool", "name": "Block 1"},
            ],
        },
        {
            "name": "Decoder Enable Even",
            "task_segments": [
                {"type": "const", "bits": 1, "value": 1, "label": "Fixed 1"},
                {"type": "uint", "name": "Decoder_Index", "bits": 2},
                {"type": "const", "bits": 1, "value": 1, "label": "Even suffix 1"},
            ],
            "config_segments": [
                {"type": "bool", "name": "Block 16"},
                {"type": "bool", "name": "Block 14"},
                {"type": "bool", "name": "Block 12"},
                {"type": "bool", "name": "Block 10"},
                {"type": "bool", "name": "Block 8"},
                {"type": "bool", "name": "Block 6"},
                {"type": "bool", "name": "Block 4"},
                {"type": "bool", "name": "Block 2"}
            ],
        },
        {
            "name": "Stim Buffer Selection",
            "task_segments": [
                {"type": "const", "bits": 1, "value": 0, "label": "Prefix 0"},
                {"type": "uint", "name": "Stim_buff", "bits": 3},
            ],
            "config_segments": [
                {"type": "uint", "name": "Row", "bits": 2},
                {"type": "uint", "name": "Col_odd", "bits": 3},
                {"type": "uint", "name": "Col_even", "bits": 3},
            ],
        },
    ],
}

class StimBufferGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = 4
        self.cols = 16
        self.cell_w = 45
        self.cell_h = 32
        self.selected_row = 0
        self.selected_col_even = 0
        self.selected_col_odd = 0
        self.setMinimumSize(self.cols * self.cell_w + 1, self.rows * self.cell_h + 1)

    def set_selection(self, row=None, col_even=None, col_odd=None):
        if row is not None:
            self.selected_row = row
        if col_even is not None:
            self.selected_col_even = col_even
        if col_odd is not None:
            self.selected_col_odd = col_odd
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        for r in range(self.rows):
            for c in range(self.cols):
                pixel = r * self.cols + c

                # Even physical columns: 0,2,4,...14 -> Col_even 0..7
                # Odd physical columns : 1,3,5,...15 -> Col_odd  0..7
                if c % 2 == 0:
                    col_type = "E"
                    col_num = c // 2
                    selected = (r == self.selected_row and col_num == self.selected_col_even)
                else:
                    col_type = "O"
                    col_num = c // 2
                    selected = (r == self.selected_row and col_num == self.selected_col_odd)

                x = c * self.cell_w
                y = r * self.cell_h
                rect = QRect(x, y, self.cell_w, self.cell_h)

                if selected:
                    painter.fillRect(rect, QColor(220, 235, 255))

                painter.setPen(QPen(Qt.black, 1))
                painter.drawRect(rect)

                text = f"{pixel}\nR{r} {col_type}{col_num}"
                painter.drawText(rect, Qt.AlignCenter, text)

        painter.end()

class ProtocolGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("14-bit Protocol Generator")
        self.resize(780, 560)
        self.setWindowIcon(QIcon("metu.ico"))
        self.command_schemas = []
        self.current_schema = None
        self.task_widgets = {}
        self.config_widgets = {}

        central = QWidget()
        self.setCentralWidget(central)

        # -------------------------
        # Top-level selectors
        # -------------------------
        self.unit_combo = QComboBox()
        for unit_code, unit_name in UNIT_NAMES.items():
            self.unit_combo.addItem(unit_name, unit_code)

        self.command_combo = QComboBox()

        # -------------------------
        # Dynamic task/config groups
        # -------------------------
        self.task_group = QGroupBox("Task Bit Fields")
        self.task_form = QFormLayout()
        self.task_group.setLayout(self.task_form)

        self.config_group = QGroupBox("Configuration Bit Fields")
        self.config_form = QFormLayout()
        self.config_group.setLayout(self.config_form)

        # -------------------------
        # Stim Address Grid (for Stim Buffer Selection command)
        # -------------------------

        self.stim_grid_group = QGroupBox("Stim Buffer Grid")
        self.stim_grid = StimBufferGrid()
        self.stim_grid_layout = QVBoxLayout()
        self.stim_grid_layout.addWidget(self.stim_grid)

        self.stim_grid_note = QLabel(
            "Pixel index: row-major order from upper-left.\n"
            "Even columns: physical columns 0,2,4,...14 → Col_even 0..7\n"
            "Odd columns: physical columns 1,3,5,...15 → Col_odd 0..7"
        )
        self.stim_grid_note.setWordWrap(True)
        self.stim_grid_layout.addWidget(self.stim_grid_note)

        self.stim_grid_group.setLayout(self.stim_grid_layout)
        self.stim_grid_group.hide()

        # -------------------------
        # Output labels
        # -------------------------
        self.unit_bits_label = QLabel()
        self.task_bits_label = QLabel()
        self.config_bits_label = QLabel()
        self.packet_bits_label = QLabel()
        self.packet_hex_label = QLabel()
        self.packet_dec_label = QLabel()
        self.info_label = QLabel()

        for label in [
            self.unit_bits_label,
            self.task_bits_label,
            self.config_bits_label,
            self.packet_bits_label,
            self.packet_hex_label,
            self.packet_dec_label,
        ]:
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setStyleSheet("font-family: Consolas, 'Courier New', monospace;")

        self.info_label.setWordWrap(True)

        clear_button = QPushButton("Clear")

        # -------------------------
        # Input layout
        # -------------------------
        input_group = QGroupBox("Inputs")
        input_layout = QGridLayout()

        input_layout.addWidget(QLabel("Unit:"), 0, 0)
        input_layout.addWidget(self.unit_combo, 0, 1)

        input_layout.addWidget(QLabel("Command:"), 1, 0)
        input_layout.addWidget(self.command_combo, 1, 1)

        input_layout.addWidget(self.task_group, 2, 0, 1, 2)
        input_layout.addWidget(self.config_group, 3, 0, 1, 2)
        input_layout.addWidget(self.stim_grid_group, 4, 0, 1, 2)
        input_layout.addWidget(clear_button, 5, 1)

        input_group.setLayout(input_layout)

        # -------------------------
        # Output layout
        # -------------------------
        output_group = QGroupBox("Output")
        output_layout = QGridLayout()

        output_layout.addWidget(QLabel("Unit bits:"), 0, 0)
        output_layout.addWidget(self.unit_bits_label, 0, 1)

        output_layout.addWidget(QLabel("Task bits:"), 1, 0)
        output_layout.addWidget(self.task_bits_label, 1, 1)

        output_layout.addWidget(QLabel("Config bits:"), 2, 0)
        output_layout.addWidget(self.config_bits_label, 2, 1)

        output_layout.addWidget(QLabel("14-bit stream:"), 3, 0)
        output_layout.addWidget(self.packet_bits_label, 3, 1)

        output_layout.addWidget(QLabel("Hex value:"), 4, 0)
        output_layout.addWidget(self.packet_hex_label, 4, 1)

        output_layout.addWidget(QLabel("Decimal value:"), 5, 0)
        output_layout.addWidget(self.packet_dec_label, 5, 1)

        output_layout.addWidget(QLabel("Notes:"), 6, 0)
        output_layout.addWidget(self.info_label, 6, 1)

        output_group.setLayout(output_layout)

        # -------------------------
        # Main layout
        # -------------------------
        main_layout = QVBoxLayout()
        main_layout.addWidget(input_group)
        main_layout.addWidget(output_group)
        central.setLayout(main_layout)

        # -------------------------
        # Signals
        # -------------------------
        self.unit_combo.currentIndexChanged.connect(self.update_command_list)
        self.command_combo.currentIndexChanged.connect(self.rebuild_dynamic_forms)
        self.command_combo.currentIndexChanged.connect(self.update_packet)
        clear_button.clicked.connect(self.clear_fields)

        self.update_command_list()
        self.update_packet()

    @staticmethod
    def to_binary(value: int, width: int) -> str:
        return format(value, f"0{width}b")

    def clear_layout(self, form_layout):
        while form_layout.rowCount():
            form_layout.removeRow(0)

    def clear_fields(self):
        self.unit_combo.setCurrentIndex(0)
        self.update_command_list()

    def update_command_list(self):
        unit = self.unit_combo.currentData()
        self.command_schemas = PROTOCOL_SCHEMAS.get(unit, [])

        self.command_combo.blockSignals(True)
        self.command_combo.clear()

        for idx, schema in enumerate(self.command_schemas):
            self.command_combo.addItem(schema["name"], idx)

        self.command_combo.blockSignals(False)
        self.rebuild_dynamic_forms()
        self.update_packet()

    def enforce_if_elseif_flags(self):
        if self.current_schema is None:
            return

        name = self.current_schema["name"]

        if name == "IV Selection & Stim Enable":
            load_vi = self.config_widgets.get("Load_VI")
            load_stim = self.config_widgets.get("Load_Stim_EN")

            if load_vi is not None and load_stim is not None:
                if load_vi.isChecked():
                    load_stim.blockSignals(True)
                    load_stim.setChecked(False)
                    load_stim.blockSignals(False)

        elif name == "P_off":
            load_res = self.config_widgets.get("Load_res")
            load_poff = self.config_widgets.get("Load_P_off")

            if load_res is not None and load_poff is not None:
                if load_res.isChecked():
                    load_poff.blockSignals(True)
                    load_poff.setChecked(False)
                    load_poff.blockSignals(False)

    def make_uint_widget(self, bits):
        widget = QLineEdit()

        # Allow only 0/1, max length = bit width
        regex = QRegularExpression(f"^[01]{{0,{bits}}}$")
        validator = QRegularExpressionValidator(regex)
        widget.setValidator(validator)

        widget.setPlaceholderText(f"{bits}-bit binary (e.g. {'1'*bits})")

        widget.textChanged.connect(self.update_packet)
        return widget

    def make_bool_widget(self):
        widget = QCheckBox()
        widget.stateChanged.connect(self.update_packet)
        return widget

    def segment_value(self, seg, widget_map):
        seg_type = seg["type"]

        if seg_type == "const":
            bits = seg["bits"]
            value = seg["value"]
            return value, bits, self.to_binary(value, bits)

        if seg_type == "reserved":
            bits = seg["bits"]
            return 0, bits, "0" * bits

        if seg_type == "bool":
            value = 1 if widget_map[seg["name"]].isChecked() else 0
            return value, 1, str(value)

        if seg_type == "uint":
            bits = seg["bits"]
            text = widget_map[seg["name"]].text().strip()

            # Empty field -> all zeros
            if text == "":
                bin_str = "0" * bits
            else:
                bin_str = text.zfill(bits)

            # Reverse entered bit order if required by the new wiring
            if seg.get("reverse_bits", False):
                bin_str = bin_str[::-1]

            value = int(bin_str, 2)
            return value, bits, bin_str

        raise ValueError(f"Unsupported segment type: {seg_type}")

    def pack_segments(self, segments, widget_map):
        value = 0
        bits_str = ""

        for seg in segments:
            seg_value, seg_bits, seg_bin = self.segment_value(seg, widget_map)
            value = (value << seg_bits) | seg_value
            bits_str += seg_bin

        return value, bits_str

    def rebuild_dynamic_forms(self):
        self.clear_layout(self.task_form)
        self.clear_layout(self.config_form)
        self.task_widgets = {}
        self.config_widgets = {}

        if self.command_combo.count() == 0:
            self.current_schema = None
            return

        schema_idx = self.command_combo.currentData()
        self.current_schema = self.command_schemas[schema_idx]

        # ----- Task dynamic fields -----
        task_segments = self.current_schema.get("task_segments", None)
        fixed_task = self.current_schema.get("fixed_task", None)

        if task_segments is None and fixed_task is not None:
            self.task_form.addRow(QLabel(f"Fixed task code: {fixed_task} ({self.to_binary(fixed_task, 4)})"))
        else:
            for seg in task_segments:
                if seg["type"] == "uint":
                    widget = self.make_uint_widget(seg["bits"])
                    self.task_widgets[seg["name"]] = widget
                    self.task_form.addRow(f'{seg["name"]} <{seg["bits"]-1}:0>:', widget)
                elif seg["type"] == "bool":
                    widget = self.make_bool_widget()
                    self.task_widgets[seg["name"]] = widget
                    self.task_form.addRow(seg["name"] + ":", widget)
                else:
                    label = seg.get("label", f'{seg["type"]} ({seg["bits"]} bits)')
                    self.task_form.addRow(QLabel(label))

        # ----- Config dynamic fields -----
        for seg in self.current_schema["config_segments"]:
            if seg["type"] == "uint":
                widget = self.make_uint_widget(seg["bits"])
                self.config_widgets[seg["name"]] = widget
                self.config_form.addRow(f'{seg["name"]} <{seg["bits"]-1}:0>:', widget)

            elif seg["type"] == "bool":
                widget = self.make_bool_widget()
                self.config_widgets[seg["name"]] = widget
                self.config_form.addRow(seg["name"] + ":", widget)

            elif seg["type"] == "const":
                label = seg.get("label", f'Const {seg["value"]}')
                self.config_form.addRow(QLabel(f'{label} ({self.to_binary(seg["value"], seg["bits"])})'))

            elif seg["type"] == "reserved":
                label = seg.get("label", "Reserved")
                self.config_form.addRow(QLabel(f'{label} ({seg["bits"]} bit{"s" if seg["bits"] > 1 else ""})'))

        if self.current_schema["name"] == "Stim Buffer Selection":
            self.stim_grid_group.show()
        else:
            self.stim_grid_group.hide()

        

        self.update_packet()

    def get_task_value_and_bits(self):
        if self.current_schema is None:
            return None, None

        if "fixed_task" in self.current_schema:
            task = self.current_schema["fixed_task"]
            return task, self.to_binary(task, 4)

        task, task_bits = self.pack_segments(
            self.current_schema["task_segments"],
            self.task_widgets
        )
        return task, task_bits

    def get_config_value_and_bits(self):
        if self.current_schema is None:
            return None, None

        config, config_bits = self.pack_segments(
            self.current_schema["config_segments"],
            self.config_widgets
        )
        return config, config_bits

    def update_packet(self):
        unit = self.unit_combo.currentData()

        if self.current_schema is None:
            self.unit_bits_label.setText(self.to_binary(unit, 2))
            self.task_bits_label.setText("----")
            self.config_bits_label.setText("--------")
            self.packet_bits_label.setText("No command selected")
            self.packet_hex_label.setText("-")
            self.packet_dec_label.setText("-")
            self.info_label.setText("")
            return

        task, task_bits = self.get_task_value_and_bits()
        config, config_bits = self.get_config_value_and_bits()

        if task is None or config is None:
            self.packet_bits_label.setText("Invalid")
            return

        packet = (unit << 12) | (task << 8) | config
        packet_bits = self.to_binary(packet, 14)
        formatted_bits = f"{packet_bits[0:2]} {packet_bits[2:6]} {packet_bits[6:14]}"

        self.unit_bits_label.setText(self.to_binary(unit, 2))
        self.task_bits_label.setText(task_bits)
        self.config_bits_label.setText(config_bits)
        self.packet_bits_label.setText(formatted_bits)
        self.packet_hex_label.setText(f"0x{packet:04X}")
        self.packet_dec_label.setText(str(packet))

        notes = []
        if self.current_schema["name"] in ("Coating/Shorting", "ADC Start"):
            notes.append("Config bits are treated as 0 because the sheet marks them as don't care.")
        if self.current_schema["name"] == "P_off":
            notes.append("The leading X bit is encoded as 0 by default.")
        if self.current_schema["name"] in ("Decoder Enable Odd", "Decoder Enable Even"):
            notes.append("Task bits use the 1XX0 / 1XX1 convention from the sheet.")
        if self.current_schema["name"] == "Stim Buffer Selection":
            notes.append("Task bits include Stim_buff<2:0>; config packs Row, Col_odd, Col_even.")

        self.info_label.setText(" ".join(notes))
        
        if self.current_schema["name"] == "Stim Buffer Selection":
            row_text = self.config_widgets["Row"].text().strip()
            col_odd_text = self.config_widgets["Col_odd"].text().strip()
            col_even_text = self.config_widgets["Col_even"].text().strip()

            row = int(row_text.zfill(2), 2) if row_text else 0
            col_odd = int(col_odd_text.zfill(3), 2) if col_odd_text else 0
            col_even = int(col_even_text.zfill(3), 2) if col_even_text else 0

            self.stim_grid.set_selection(
                row=row,
                col_even=col_even,
                col_odd=col_odd
            )

        self.enforce_if_elseif_flags()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProtocolGui()
    window.show()
    sys.exit(app.exec())