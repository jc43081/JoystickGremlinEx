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
import os
import re

from PySide6 import QtWidgets, QtCore, QtGui

import gremlin, logging
import gremlin.ui.ui_common


class ScVjoyMapperUI(gremlin.ui.ui_common.BaseDialogUi):

    """Allows the creation of a controlized Controls Profile 
    for the current Star Citize vJoy Mapping"""

    def __init__(self, parent=None):
        """Creates a new instance.

        :param profile_data complete profile data
        :param parent the parent of this widget
        """
        super().__init__(parent)

        self.logger = logging.getLogger("system")
        self.base_control_profile = gremlin.util.userprofile_path()
        self.reg_vjoy_order = reg=re.compile('1-5],')
        self.vjoy_ordering = "1,2,3,4,5"
        self.sc_installation = "C:\\Program Files\\Robert Space Industries\\Star Citizen\\LIVE"

        self.logger.info("Starting SC vJoy Mapper")
        self.setWindowTitle("SC vJoy Mapper")

        self.main_layout = QtWidgets.QVBoxLayout(self)

        # Get the desired order of vJoy to use as a base
        vjoy_ordering_labels = QtWidgets.QLabel("vJoy Order:")
        vjoy_ordering_edit = QtWidgets.QHBoxLayout()
        self.vjoy_ordering_textbox = QtWidgets.QLineEdit()
        self.vjoy_ordering_textbox.setText(self.vjoy_ordering)
        self.vjoy_ordering_textbox.setFixedWidth(100)
        self.vjoy_ordering_textbox.textEdited.connect(self._update_vjoy_ordering)
        vjoy_ordering_edit.addWidget(self.vjoy_ordering_textbox)
        vjoy_ordering_edit.addWidget(QtWidgets.QLabel("(Enter 5 numbers (1-5) separated by commas)"))

        vjoy_ordering_layout = QtWidgets.QFormLayout()
        vjoy_ordering_layout.addRow(vjoy_ordering_labels, vjoy_ordering_edit)
        self.main_layout.addLayout(vjoy_ordering_layout)

        # Get the Control Profile to use as a base
        control_profile_labels = QtWidgets.QLabel("Base Control Profile:")
        self.control_profile_textbox = QtWidgets.QLineEdit()
        self.control_profile_textbox.setText(self.base_control_profile)
        self.control_profile_textbox.textEdited.connect(self._update_control_profile)

        control_profile_button = QtWidgets.QPushButton("Select Control Profile XML")
        control_profile_button.clicked.connect(self._show_control_profile_picker)

        control_profile_layout = QtWidgets.QFormLayout()
        control_profile_layout.addRow(control_profile_labels, self.control_profile_textbox)
        control_profile_layout.addWidget(control_profile_button)
        #control_profile_layout.addStretch()
        self.main_layout.addLayout(control_profile_layout)

        # Get the current location of the Star Citizen folder
        sc_installation_labels = QtWidgets.QLabel("Star Citizen Installation:")
        self.sc_installation_textbox = QtWidgets.QLineEdit()
        self.sc_installation_textbox.setText(self.sc_installation)
        self.sc_installation_textbox.textEdited.connect(self._update_sc_installation)        

        sc_installation_button = QtWidgets.QPushButton("Select SC Folder")
        sc_installation_button.clicked.connect(self._show_sc_installation_picker)

        # Get the Directory for Star Citizen version to update
        sc_installation_layout = QtWidgets.QFormLayout()
        sc_installation_layout.addRow(sc_installation_labels, self.sc_installation_textbox)
        sc_installation_layout.addWidget(sc_installation_button)
        self.main_layout.addLayout(sc_installation_layout)

        # Put the instructions on how to use
        instruction_layout = QtWidgets.QVBoxLayout()
        instruction_layout.addWidget(QtWidgets.QLabel("<b>Instructions:<b>\n"))
        instruction_layout.addWidget(QtWidgets.QLabel("   1. Retrieve the current vJoy order in SC (Use vJoyCheck profile found on Nexus).\n"))
        instruction_layout.addWidget(QtWidgets.QLabel("   2. In SC, return to the Main Menu. (if not, the Control Profile will not refresh).\n"))
        instruction_layout.addWidget(QtWidgets.QLabel("   3. Enter the order in vJoy Order field above.\n"))
        instruction_layout.addWidget(QtWidgets.QLabel("   4. Select the downloaded Control Profile file to use (match your SC version).\n"))
        instruction_layout.addWidget(QtWidgets.QLabel("   5. Select the location of your Star Citizen install (select LIVE, PTU, ETU to indicate environment).\n"))
        instruction_button = QtWidgets.QPushButton("5. Click HERE to run Mapper")
        instruction_button.clicked.connect(self._run_sc_mapper)
        instruction_layout.addWidget(instruction_button)
        self.main_layout.addLayout(instruction_layout)


    def _update_vjoy_ordering(self):
        self.vjoy_ordering = self.vjoy_ordering_textbox.displayText()

    def _update_control_profile(self):
        self.base_control_profile = self.control_profile_textbox.displayText()

    def _update_sc_installation(self):
        self.sc_installation = os.path.normcase(os.path.abspath(self.sc_installation_textbox.displayText()))

    def _show_control_profile_picker(self):
        options = QtWidgets.QFileDialog.Options()
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File", self.base_control_profile, "XML Files (*.xml)", options=options)

        if file_name:
            self.base_control_profile = file_name
            self.control_profile_textbox.setText(file_name)
            self.logger.debug(f"Selected file: {file_name}")


    def _show_sc_installation_picker(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.Option.ShowDirsOnly
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory", self.sc_installation, options=options)

        if directory:
            self.sc_installation = directory
            self.sc_installation_textbox.setText(directory)
            self.logger.debug(f"Selected directory: {directory}")
       

    def _match(self, strg, search=re.compile(r'[^1-5,]').search):
        return not bool(search(strg))       

    def _run_sc_mapper(self):
        self.logger.info(f"Running the mapper")  
        self.logger.debug(f"vJoy Order: {self.vjoy_ordering}")
        self.logger.debug(f"control Profile: {self.base_control_profile}")
        self.logger.debug(f"SC Installation: {self.sc_installation}")

        vjoy_order = self.vjoy_ordering.split(",")
        if self._match(self.vjoy_ordering) == False or len(vjoy_order) != 5:
            gremlin.util.display_error("vJoy Order must have 5 numbers (1-5) separated by commas")
            return

        if os.path.exists(self.base_control_profile) == False or self.base_control_profile.endswith(".xml") == False:
            gremlin.util.display_error("Control Profile was not found or not an XML file. Please pick a SC Control Profile.")
            return
        
        if os.path.exists(self.sc_installation+"\\StarCitizen_Launcher.exe") == False:
            gremlin.util.display_error("Star Citizen Installation folder is not correct. Please pick the correct location")
            return
        
        try:
            self.logger.debug(f"Reading Control Profile")
            with open(self.base_control_profile, "r") as control_profile_file:
                control_profile = control_profile_file.read()

        finally:
            control_profile_file.close()

        self.logger.debug(f"Starting remap...")
        # Map with a placeholder to avoid replacing too much
        i = 1
        for vjoy in vjoy_order:
            control_profile = control_profile.replace(f"js{i}_", f"holding{vjoy}_")
            i = i + 1

        for i in range(1,6):
            control_profile = control_profile.replace(f"holding{i}_", f"js{i}_")

        self.logger.debug(f"Completed remap...")

        file_name = os.path.basename(self.base_control_profile)
        control_profile_sc = os.path.join(self.sc_installation,f"user\\client\\0\\Controls\\Mappings\\{file_name}")
        try:
            self.logger.debug(f"Writing out Control Profile")
            with open(control_profile_sc, "w") as control_profile_sc_file:
                control_profile_sc_file.write(control_profile)

        finally:
            control_profile_sc_file.close()

        box = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Icon.Information,
            "Info",
            "The updated Control Profile is now ready!\n\nImport the profile into Star Citizen again to update it with the new mappings.",
            QtWidgets.QMessageBox.Ok
        )
        box.exec()          