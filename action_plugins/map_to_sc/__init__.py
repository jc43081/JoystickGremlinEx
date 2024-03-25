# -*- coding: utf-8; -*-

# Copyright (C) 2015 - 2019 Lionel Ott
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import logging
import threading
import time
from xml.etree import ElementTree

from PySide6 import QtWidgets, QtCore

from gremlin.base_classes import InputActionCondition
from gremlin.common import InputType
from gremlin import input_devices, joystick_handling, util
from gremlin.error import ProfileError
from gremlin.profile import safe_format, safe_read
import gremlin.ui.common
import gremlin.ui.input_item
import gremlin.ui.device_tab


class MapToScWidget(gremlin.ui.input_item.AbstractActionWidget):

    """Dialog which allows the selection of a vJoy output to use as
    as the remapping for the currently selected input.
    """

    controls_description_changed = QtCore.Signal()

    # Mapping from types to display names
    type_to_name_map = {
        InputType.JoystickAxis: "Axis",
        InputType.JoystickButton: "Button",
        InputType.JoystickHat: "Hat",
        InputType.Keyboard: "Button",
    }
    name_to_type_map = {
        "Axis": InputType.JoystickAxis,
        "Button": InputType.JoystickButton,
        "Hat": InputType.JoystickHat
    }

    def __init__(self, action_data, parent=None):
        """Creates a new MapToScWidget.

        :param action_data profile data managed by this widget
        :param parent the parent of this widget
        """
        super().__init__(action_data, parent=parent)
        assert(isinstance(action_data, MapToSc))

    def _create_ui(self):
        """Creates the UI components."""
        input_types = {
            InputType.Keyboard: [
                InputType.JoystickButton
            ],
            InputType.JoystickAxis: [
                InputType.JoystickAxis,
                InputType.JoystickButton
            ],
            InputType.JoystickButton: [
                InputType.JoystickButton
            ],
            InputType.JoystickHat: [
                InputType.JoystickButton,
                InputType.JoystickHat
            ]
        }
        self.controls_selector = ControlsSelector(
            lambda x: self.save_controls_changes(),
            input_types[self._get_input_type()]
        )
        self.main_layout.addWidget(self.controls_selector)

        # Create UI widgets for absolute / relative axis modes if the remap
        # action is being added to an axis input type
        if self.action_data.get_input_type() == InputType.JoystickAxis:
            self.maptosc_type_widget = QtWidgets.QWidget()
            self.maptosc_type_layout = QtWidgets.QHBoxLayout(self.maptosc_type_widget)


            self.absolute_checkbox = QtWidgets.QRadioButton("Absolute")
            self.absolute_checkbox.setChecked(True)
            self.relative_checkbox = QtWidgets.QRadioButton("Relative")
            self.relative_scaling = gremlin.ui.common.DynamicDoubleSpinBox()

            self.maptosc_type_layout.addStretch()
            self.maptosc_type_layout.addWidget(self.absolute_checkbox)
            self.maptosc_type_layout.addWidget(self.relative_checkbox)
            self.maptosc_type_layout.addWidget(self.relative_scaling)
            self.maptosc_type_layout.addWidget(QtWidgets.QLabel("Scale"))

            self.maptosc_type_widget.hide()
            self.main_layout.addWidget(self.maptosc_type_widget)

            # The widgets should only be shown when we actually map to an axis
            if self.action_data.input_type == InputType.JoystickAxis:
                self.maptosc_type_widget.show()

        self.main_layout.setContentsMargins(0, 0, 0, 0)

    def _populate_ui(self):
        """Populates the UI components."""

        # Set the initial category and controls ids
        if (self.action_data.category_id != None):
            category_id = self.action_data.category_id
        else:
            category_id = self.controls_selector.category_list[0]["id"]
        if (self.action_data.controls_id != None):
            controls_id = self.action_data.controls_id
        else:
            controls_id = self.controls_selector.controls_list[0]["values"][0]["id"]

        # Get the appropriate vjoy device identifier
        vjoy_dev_id = 0
        if self.action_data.vjoy_device_id not in [0, None]:
            vjoy_dev_id = self.action_data.vjoy_device_id

        # Get the input type which can change depending on the container used
        input_type = self.action_data.input_type
        if self.action_data.parent.tag == "hat_buttons":
            input_type = InputType.JoystickButton

        # Handle obscure bug which causes the action_data to contain no
        # input_type information
        if input_type is None:
            input_type = InputType.JoystickButton
            logging.getLogger("system").warning("None as input type encountered")

        try:
            self.controls_selector.set_selection(
                input_type,
                category_id,
                controls_id
            )

            if self.action_data.input_type == InputType.JoystickAxis:
                if self.action_data.axis_mode == "absolute":
                    self.absolute_checkbox.setChecked(True)
                else:
                    self.relative_checkbox.setChecked(True)
                self.relative_scaling.setValue(self.action_data.axis_scaling)

                self.absolute_checkbox.clicked.connect(self.save_controls_changes)
                self.relative_checkbox.clicked.connect(self.save_controls_changes)
                self.relative_scaling.valueChanged.connect(self.save_controls_changes)

            # Save changes so the UI updates properly
            self.save_controls_changes()
        except gremlin.error.GremlinError as e:
            util.display_error(
                "A needed vJoy device is not accessible: {}\n\n".format(e) +
                "Default values have been set for the input, but they are "
                "not what has been specified."
            )
            logging.getLogger("system").error(str(e))

    def save_controls_changes(self):
        """Saves UI contents to the profile data storage."""
        # Store map to sc data
        try:
            controls_data = self.controls_selector.get_selection()
            input_type_changed = \
                self.action_data.input_type != controls_data["input_type"]
            controls_changed = \
                self.action_data.controls_id != controls_data["controls_id"]
            self.action_data.category_id = controls_data["category_id"]
            self.action_data.controls_id = controls_data["controls_id"]
            self.action_data.input_type = controls_data["input_type"]
            self.action_data.vjoy_device_id = controls_data["vjoy_device_id"]
            self.action_data.vjoy_input_id = controls_data["vjoy_input_id"]
            self.action_data.parent_input_item.description = controls_data["description"]
            el = gremlin.event_handler.EventListener()
            el.action_description_changed.emit()

            if self.action_data.input_type == InputType.JoystickAxis:
                self.action_data.axis_mode = "absolute"
                if self.relative_checkbox.isChecked():
                    self.action_data.axis_mode = "relative"
                self.action_data.axis_scaling = self.relative_scaling.value()

            # Signal changes
            if input_type_changed or controls_changed:
                self.action_modified.emit()
        except gremlin.error.GremlinError as e:
            logging.getLogger("system").error(str(e))


class MapToScFunctor(gremlin.base_classes.AbstractFunctor):

    """Executes a Map to Star Citizen action when called."""

    def __init__(self, action):
        super().__init__(action)
        self.vjoy_device_id = action.vjoy_device_id
        self.vjoy_input_id = action.vjoy_input_id
        self.input_type = action.input_type
        self.axis_mode = action.axis_mode
        self.axis_scaling = action.axis_scaling

        self.needs_auto_release = self._check_for_auto_release(action)
        self.thread_running = False
        self.should_stop_thread = False
        self.thread_last_update = time.time()
        self.thread = None
        self.axis_delta_value = 0.0
        self.axis_value = 0.0

    def process_event(self, event, value):
        if self.input_type == InputType.JoystickAxis:
            if self.axis_mode == "absolute":
                joystick_handling.VJoyProxy()[self.vjoy_device_id] \
                    .axis(self.vjoy_input_id).value = value.current
            else:
                self.should_stop_thread = abs(event.value) < 0.05
                self.axis_delta_value = \
                    value.current * (self.axis_scaling / 1000.0)
                self.thread_last_update = time.time()
                if self.thread_running is False:
                    if isinstance(self.thread, threading.Thread):
                        self.thread.join()
                    self.thread = threading.Thread(
                        target=self.relative_axis_thread
                    )
                    self.thread.start()

        elif self.input_type == InputType.JoystickButton:
            if event.event_type in [InputType.JoystickButton, InputType.Keyboard] \
                    and event.is_pressed \
                    and self.needs_auto_release:
                input_devices.ButtonReleaseActions().register_button_release(
                    (self.vjoy_device_id, self.vjoy_input_id),
                    event
                )

            joystick_handling.VJoyProxy()[self.vjoy_device_id] \
                .button(self.vjoy_input_id).is_pressed = value.current

        elif self.input_type == InputType.JoystickHat:
            joystick_handling.VJoyProxy()[self.vjoy_device_id] \
                .hat(self.vjoy_input_id).direction = value.current

        return True

    def relative_axis_thread(self):
        self.thread_running = True
        vjoy_dev = joystick_handling.VJoyProxy()[self.vjoy_device_id]
        self.axis_value = vjoy_dev.axis(self.vjoy_input_id).value
        while self.thread_running:
            try:
                # If the vjoy value has was changed from what we set it to
                # in the last iteration, terminate the thread
                change = vjoy_dev.axis(self.vjoy_input_id).value - self.axis_value
                if abs(change) > 0.0001:
                    self.thread_running = False
                    self.should_stop_thread = True
                    return

                self.axis_value = max(
                    -1.0,
                    min(1.0, self.axis_value + self.axis_delta_value)
                )
                vjoy_dev.axis(self.vjoy_input_id).value = self.axis_value

                if self.should_stop_thread and \
                        self.thread_last_update + 1.0 < time.time():
                    self.thread_running = False
                time.sleep(0.01)
            except gremlin.error.VJoyError:
                self.thread_running = False

    def _check_for_auto_release(self, action):
        activation_condition = None
        if action.parent.activation_condition:
            activation_condition = action.parent.activation_condition
        elif action.activation_condition:
            activation_condition = action.activation_condition

        # If an input action activation condition is present the auto release
        # may have to be disabled
        needs_auto_release = True
        if activation_condition:
            for condition in activation_condition.conditions:
                if isinstance(condition, InputActionCondition):
                    # Remap like actions typically have an always activation
                    # condition associated with them
                    if condition.comparison != "always":
                        needs_auto_release = False

        return needs_auto_release


class MapToSc(gremlin.base_classes.AbstractAction):

    """Action remapping physical joystick inputs to Game-defined inputs."""

    name = "Map To SC"
    tag = "maptosc"

    default_button_activation = (True, True)
    input_types = [
        InputType.JoystickAxis,
        InputType.JoystickButton,
        InputType.JoystickHat,
        InputType.Keyboard
    ]

    functor = MapToScFunctor
    widget = MapToScWidget

    def __init__(self, parent):
        """Creates a new instance.

        :param parent the container to which this action belongs
        """
        super().__init__(parent)

        # Set vjoy ids to None so we know to pick the next best one
        # automatically
        self.vjoy_device_id = None
        self.vjoy_input_id = None
        self.input_type = self.parent.parent.input_type
        self.axis_mode = "absolute"
        self.axis_scaling = 1.0
        self.category_id = None
        self.controls_id = None
        self.parent_input_item = parent.parent

    def icon(self):
        """Returns the icon corresponding to the remapped input.

        :return icon representing the remap action
        """

        # For now, use standard icon
        return f"action_plugins/map_to_sc/icon.png"

    def requires_virtual_button(self):
        """Returns whether or not the action requires an activation condition.

        :return True if an activation condition is required, False otherwise
        """
        input_type = self.get_input_type()

        if input_type in [InputType.JoystickButton, InputType.Keyboard]:
            return False
        elif input_type == InputType.JoystickAxis:
            if self.input_type == InputType.JoystickAxis:
                return False
            else:
                return True
        elif input_type == InputType.JoystickHat:
            if self.input_type == InputType.JoystickHat:
                return False
            else:
                return True

    def _parse_xml(self, node):
        """Populates the data storage with data from the XML node.

        :param node XML node with which to populate the storage
        """
        try:
            if "axis" in node.attrib:
                self.input_type = InputType.JoystickAxis
                self.vjoy_input_id = safe_read(node, "axis", int)
            elif "button" in node.attrib:
                self.input_type = InputType.JoystickButton
                self.vjoy_input_id = safe_read(node, "button", int)
            elif "hat" in node.attrib:
                self.input_type = InputType.JoystickHat
                self.vjoy_input_id = safe_read(node, "hat", int)
            elif "keyboard" in node.attrib:
                self.input_type = InputType.Keyboard
                self.vjoy_input_id = safe_read(node, "button", int)
            else:
                raise gremlin.error.GremlinError(
                    "Invalid input type provided: {}".format(node.attrib)
                )

            self.vjoy_device_id = safe_read(node, "vjoy", int)
            self.category_id = safe_read(node, "category", int)
            self.controls_id = safe_read(node, "controls", int)

            if self.get_input_type() == InputType.JoystickAxis and \
                    self.input_type == InputType.JoystickAxis:
                self.axis_mode = safe_read(node, "axis-type", str, "absolute")
                self.axis_scaling = safe_read(node, "axis-scaling", float, 1.0)
        except ProfileError:
            self.vjoy_input_id = None
            self.vjoy_device_id = None
            self.category_id = None
            self.controls_id = None

    def _generate_xml(self):
        """Returns an XML node encoding this action's data.

        :return XML node containing the action's data
        """
        node = ElementTree.Element("maptosc")
        node.set("vjoy", str(self.vjoy_device_id))
        if self.input_type == InputType.Keyboard:
            node.set(
                InputType.to_string(InputType.JoystickButton),
                str(self.vjoy_input_id)
            )
        else:
            node.set(
                InputType.to_string(self.input_type),
                str(self.vjoy_input_id)
            )
        node.set("category", str(self.category_id))
        node.set("controls", str(self.controls_id))

        if self.get_input_type() == InputType.JoystickAxis and \
                self.input_type == InputType.JoystickAxis:
            node.set("axis-type", safe_format(self.axis_mode, str))
            node.set("axis-scaling", safe_format(self.axis_scaling, float))

        return node

    def _is_valid(self):
        """Returns whether or not the action is configured properly.

        :return True if the action is configured correctly, False otherwise
        """

                
        # TODO: Update this with real once understood
        #return not(self.vjoy_device_id is None or self.vjoy_input_id is None)
        return True
        


class ControlsSelector(QtWidgets.QWidget):

    """
        Create a Selector that can allows for managing a category and 
        the allowed controls within that category.
    
        Category will provide the valid list of controls.
        Controls will be mapped to proper vJoy Device and Input

        
    """

    def __init__(self, change_cb, valid_types, parent=None):
        super().__init__(parent)

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.change_cb = change_cb
        self.valid_types = valid_types

        self.category_list = [  { 
                                    "name": "Flight",
                                    "id": 10 
                                },
                                {
                                    "name": "Turret",
                                    "id": 20
                                },
                                {
                                    "name": "Targeting",
                                    "id": 30
                                }]
        self.controls_list = [
            {
                "category_id": 10,
                "values": [ 
                            { "name": "Pitch", "id": 11, "type": "axis", "vjoy": 1, "axis": 2},
                            { "name": "Yaw", "id": 21, "type": "axis", "vjoy": 1, "axis": 3 },
                            { "name": "Roll", "id": 31, "type": "axis", "vjoy": 1, "axis": 1 }
                        ]
            },
            {
                "category_id": 20,
                "values": [ 
                            { "name": "Recenter", "id": 12, "type": "button", "vjoy": 1, "button": 1 },
                            { "name": "Fire Mode", "id": 22, "type": "button", "vjoy": 1, "button": 2  },
                            { "name": "Gyro", "id": 32, "type": "button", "vjoy": 1, "button": 3  }
                        ]
            },
            {
                "category_id": 30,
                "values": [ 
                            { "name": "Pin Selected", "id": 15, "type": "button", "vjoy": 1, "button": 4 },
                            { "name": "Cycle Selection", "id": 25, "type": "button", "vjoy": 1, "button": 5 },
                            { "name": "Lock Selected", "id": 35, "type": "button", "vjoy": 1, "button": 6 }
                        ]
            }
        ]

        self.category_dropdown = None
        self.controls_dropdown = None
        self.category_registry = []
        self.controls_registry = []

        self._create_category_dropdown()
        self._create_controls_dropdown()

    def get_selection(self):
        category_id = None
        controls_id = None
        input_type = None
        vjoy_device_id = None
        vjoy_input_id = None

        if (self.category_dropdown != None):
            category_id = self.category_list[self.category_dropdown.currentIndex()]["id"]
        if (self.controls_dropdown != None):
            control_index = self.controls_dropdown[self.category_dropdown.currentIndex()].currentIndex()
            control = next((x for x in self.controls_list if x["category_id"] == category_id), None)
            controls_id = control["values"][control_index]["id"]
            vjoy_device_id = control["values"][control_index]["vjoy"]
            vjoy_input_type = control["values"][control_index]["type"]
            if "axis" in vjoy_input_type:
                vjoy_input_id = control["values"][control_index]["axis"]
            elif "button" in vjoy_input_type:
                vjoy_input_id = control["values"][control_index]["button"]
            elif "hat" in vjoy_input_type:
                vjoy_input_id = control["values"][control_index]["hat"]
            elif "keyboard" in vjoy_input_type:
                vjoy_input_id = control["values"][control_index]["keyboard"]
         
        input_type = self.valid_types[0]
        description = self.category_list[self.category_dropdown.currentIndex()]["name"] + " - " + self.controls_list[self.category_dropdown.currentIndex()]["values"][control_index]["name"]

        return {
            "category_id": category_id,
            "controls_id": controls_id,
            "input_type": input_type,
            "vjoy_device_id": vjoy_device_id,
            "vjoy_input_id": vjoy_input_id,
            "description": description
        }

    def set_selection(self, input_type, category_id, controls_id):
        if category_id not in self.category_registry:
            return

        control = next((x for x in self.controls_list if x["category_id"] == category_id), None)
        if next((x for x in control["values"] if x["id"] == controls_id), None) == None:
            return

        # # Get the index of the combo box associated with this category
        category_index = [index for (index, category) in enumerate(self.category_registry) if category == category_id][0]

        # Select and display correct combo boxes and entries within
        self.category_dropdown.setCurrentIndex(category_index)

        # Retrieve the index of the correct entry in the combobox
        control_index = [index for (index, value) in enumerate(control["values"]) if value["id"] == controls_id][0]

        # Select and display correct combo boxes and entries within
        for entry in self.controls_dropdown:
            entry.setVisible(False)
        self.controls_dropdown[category_index].setCurrentIndex(control_index)
        self.controls_dropdown[category_index].setVisible(True)

    def _update_category(self, index):
        # Hide all selection dropdowns
        for entry in self.controls_dropdown:
            entry.setVisible(False)

        # Show correct dropdown
        self.controls_dropdown[index].setVisible(True)
        self.controls_dropdown[index].setCurrentIndex(0)
        self._execute_callback()


    def _create_category_dropdown(self):
        self.category_dropdown = QtWidgets.QComboBox(self)
        for category in self.category_list:
            self.category_dropdown.addItem(category["name"])
            self.category_registry.append(category["id"])
        self.main_layout.addWidget(self.category_dropdown)
        self.category_dropdown.activated.connect(self._update_category)
        

    def _create_controls_dropdown(self):
        self.controls_dropdown = []
        self.controls_registry = []

        # Create controls selections for the category. Each selection
        # will be invisible unless it is selected as the active category
        for category in self.category_list:
            selection = QtWidgets.QComboBox(self)
            selection.setMaxVisibleItems(20)
            self.controls_registry.append({ "category_id": category["id"], "values": [] })
            
            # Add items based on the controls type
            max_col = 32
            controls = next((x for x in self.controls_list if x["category_id"] == category["id"]), None)
            for control in controls["values"]:
                selection.addItem(control["name"])
                self.controls_registry[-1]["values"].append(control["id"])

            # Add the selection and hide it
            selection.setVisible(False)
            selection.activated.connect(self._execute_callback)
            self.main_layout.addWidget(selection)
            self.controls_dropdown.append(selection)

            selection.currentIndexChanged.connect(self._execute_callback)

        # Show the first entry by default
        if len(self.controls_dropdown) > 0:
            self.controls_dropdown[0].setVisible(True)
   

    def _execute_callback(self):
        self.change_cb(self.get_selection())

version = 1
name = "map-to-sc"
create = MapToSc
