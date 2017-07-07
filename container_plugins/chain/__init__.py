# -*- coding: utf-8; -*-

# Copyright (C) 2015 - 2017 Lionel Ott
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

from PyQt5 import QtWidgets

from xml.etree import ElementTree

from mako.template import Template

import gremlin
import gremlin.ui.common
import gremlin.ui.input_item


class ChainContainerWidget(gremlin.ui.input_item.AbstractContainerWidget):

    """Container which holds a sequence of actions."""

    def __init__(self, profile_data, parent=None):
        """Creates a new instance.

        :param profile_data the profile data represented by this widget
        :param parent the parent of this widget
        """
        super().__init__(profile_data, parent)

    def _create_ui(self):
        """Creates the UI components."""
        self.widget_layout = QtWidgets.QHBoxLayout()

        self.action_selector = gremlin.ui.common.ActionSelector(
            self.profile_data.get_input_type()
        )
        self.action_selector.action_added.connect(self._add_action)
        self.widget_layout.addWidget(self.action_selector)

        self.widget_layout.addStretch(1)

        self.widget_layout.addWidget(QtWidgets.QLabel("<b>Timeout:</b> "))
        self.timeout_input = QtWidgets.QDoubleSpinBox()
        self.timeout_input.setRange(0.0, 3600.0)
        self.timeout_input.setSingleStep(0.5)
        self.timeout_input.setValue(0)
        self.timeout_input.setValue(self.profile_data.timeout)
        self.timeout_input.valueChanged.connect(self._timeout_changed_cb)
        self.widget_layout.addWidget(self.timeout_input)

        self.main_layout.addLayout(self.widget_layout)

        # Insert action widgets
        for i, action in enumerate(self.profile_data.actions):
            self.main_layout.addWidget(
                self._add_action_widget(
                    action.widget(action),
                    "Action {:d}".format(i)
                )
            )

    def _add_action(self, action_name):
        """Adds a new action to the container.

        :param action_name the name of the action to add
        """
        plugin_manager = gremlin.plugin_manager.ActionPlugins()
        action_item = plugin_manager.get_class(action_name)(self.profile_data)
        self.profile_data.add_action(action_item)
        self.modified.emit()

    def _timeout_changed_cb(self, value):
        """Stores changes to the timeout element.

        :param value the new value of the timeout field
        """
        self.profile_data.timeout = value

    def _handle_interaction(self, widget, action):
        """Handles interaction icons being pressed on the individual actions.

        :param widget the action widget on which an action was invoked
        :param action the type of action being invoked
        """
        # Find the index of the widget that gets modified
        index = self._get_widget_index(widget)

        # Perform action
        if action == gremlin.ui.input_item.ActionWrapper.Interactions.Up:
            if index > 0:
                self.profile_data.actions[index],\
                    self.profile_data.actions[index-1] = \
                    self.profile_data.actions[index-1],\
                    self.profile_data.actions[index]
        if action == gremlin.ui.input_item.ActionWrapper.Interactions.Down:
            if index < len(self.profile_data.actions) - 1:
                self.profile_data.actions[index], \
                    self.profile_data.actions[index + 1] = \
                    self.profile_data.actions[index + 1], \
                    self.profile_data.actions[index]
        if action == gremlin.ui.input_item.ActionWrapper.Interactions.Delete:
            del self.profile_data.actions[index]

        self.modified.emit()

    def _get_window_title(self):
        """Returns the title to use for this container.

        :return title to use for the container
        """
        return "Chain: {}".format(" -> ".join(
            [item.name for item in self.profile_data.actions])
        )


class ChainContainer(gremlin.base_classes.AbstractContainer):

    """Represents a container which holds multiplier actions.

    The actions will trigger one after the other with subsequent activations.
    A timeout, if set, will reset the sequence to the beginning.
    """

    name = "Chain"
    tag = "chain"
    widget = ChainContainerWidget
    input_types = [
        gremlin.common.InputType.JoystickButton,
        gremlin.common.InputType.Keyboard
    ]
    interaction_types = [
        gremlin.ui.input_item.ActionWrapper.Interactions.Up,
        gremlin.ui.input_item.ActionWrapper.Interactions.Down,
        gremlin.ui.input_item.ActionWrapper.Interactions.Delete,
    ]

    def __init__(self, parent=None):
        """Creates a new instance.

        :param parent the InputItem this container is linked to
        """
        super().__init__(parent)
        self.timeout = 0.0

    def _parse_xml(self, node):
        """Populates the container with the XML node's contents.

        :param node the XML node with which to populate the container
        """
        self.timeout = float(node.get("timeout", 0.0))

    def _generate_xml(self):
        """Returns an XML node representing this container's data.

        :return XML node representing the data of this container
        """
        node = ElementTree.Element("container")
        node.set("type", ChainContainer.tag)
        node.set("timeout", str(self.timeout))
        for action in self.actions:
            node.append(action.to_xml())
        return node

    def _generate_code(self):
        """Returns Python code for this container.

        :return Python code for this container
        """
        super()._generate_code()
        code_id = gremlin.profile.ProfileData.next_code_id
        gremlin.profile.ProfileData.next_code_id += 1

        tpl = Template(filename="container_plugins/chain/global.tpl")
        code = gremlin.profile.CodeBlock()
        code.store("container", tpl.render(
            entry=self,
            id=code_id,
            code=code
        ))
        tpl = Template(filename="container_plugins/chain/body.tpl")
        code.store("body", tpl.render(
            entry=self,
            id=code_id,
            code=code
        ))
        return code

    def _is_container_valid(self):
        """Returns whether or not this container is configured properly.

        :return True if the container is configured properly, False otherwise
        """
        return len(self.actions) > 0


# Plugin definitions
version = 1
name = "chain"
create = ChainContainer
