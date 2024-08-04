# -*- coding: utf-8; -*-

# Based on original work by (C) Lionel Ott -  (C) EMCS 2024 and other contributors
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


import os

from PySide6 import QtWidgets, QtCore, QtGui

import gremlin.base_profile
import gremlin.event_handler
from gremlin.input_types import InputType
from gremlin.input_devices import ButtonReleaseActions
import gremlin.macro
import gremlin.shared_state

import gremlin.singleton_decorator
import gremlin.ui.ui_common
import gremlin.ui.input_item
import gremlin.gated_handler
import enum
from gremlin.profile import safe_format, safe_read
from .SimConnectData import *
import re
from lxml import etree
from xml.etree import ElementTree
from gremlin.gated_handler import *



class QHLine(QtWidgets.QFrame):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)


class CommandValidator(QtGui.QValidator):
    ''' validator for command selection '''
    def __init__(self):
        super().__init__()
        self.commands = SimConnectData().get_command_name_list()
        
        
    def validate(self, value, pos):
        clean_value = value.upper().strip()
        if not clean_value or clean_value in self.commands:
            # blank is ok
            return QtGui.QValidator.State.Acceptable
        # match all values starting with the text given
        r = re.compile(clean_value + "*")
        for _ in filter(r.match, self.commands):
            return QtGui.QValidator.State.Intermediate
        return QtGui.QValidator.State.Invalid
    
class SimconnectAicraftDefinition():
    ''' holds the data entry for a single aicraft from the MSFS config data '''
    def __init__(self, id = None, mode = None, icao_type = None, icao_manufacturer = None, icao_model = None, titles = [], path = None):
        self.icao_type = icao_type
        self.icao_manufacturer = icao_manufacturer
        self.icao_model = icao_model
        self.titles = titles
        self.path = path
        self.mode = mode
        self.key = self.display_name.lower()
        self.id = id if id else gremlin.util.get_guid()
        
        # runtime item (not saved or loaded)
        self.selected = False # for UI interation - selected mode
        self.error_status = None

    @property
    def display_name(self):
        return f"{self.icao_manufacturer} {self.icao_model}"

    @property
    def valid(self):
        ''' true if the item contains valid data '''
        return not self.error_status and self.aircraft and self.mode    
    
    def __eq__(self, other):
        ''' compares two objects '''
        return gremlin.util.compare_nocase(self.icao_type, other.icao_type) and \
            gremlin.util.compare_nocase(self.icao_manufacturer, other.icao_manufacturer) and \
            gremlin.util.compare_nocase(self.icao_manufacturer, other.icao_manufacturer) and \
            gremlin.util.compare_nocase(self.icao_model, other.icao_model)
    
    def __hash__(self):
        return (self.icao_type.lower(), self.icao_manufacturer.lower(), self.icao_model.lower()).__hash__()
   
    
class SimconnectSortMode(Enum):
    NotSet = auto()
    AicraftAscending = auto()
    AircraftDescending = auto()
    Mode = auto()

@gremlin.singleton_decorator.SingletonDecorator
class SimconnectOptions(QtCore.QObject):


    ''' holds simconnect mapper options for all actions '''
    def __init__(self):
        super().__init__()
        self._profile : gremlin.base_profile.Profile = gremlin.shared_state.current_profile
        self._mode_list = self._profile.get_modes()
        self._xml_source = os.path.join(gremlin.util.userprofile_path(),"simconnect_config.xml")
        self._auto_mode_select = True # if set, autoloads the mode associated with the aircraft if such a mode exists
        self._aircraft_definitions = [] # holds aicraft entries
        self._titles = []
        self._community_folder = r"C:\Microsoft Flight Simulator\Community"
        self._sort_mode = SimconnectSortMode.NotSet
        self.parse_xml()


    @property
    def current_aircraft_folder(self):
        if self._sm.ok:
            return self._aircraft_folder
        return None
    
    @property 
    def current_aircraft_title(self):
        if self._sm.ok:
            return self._aircraft_title
        return None
    
    @property
    def community_folder(self):
        return self._community_folder
    @community_folder.setter
    def community_folder(self, value):
        self._community_folder = value

        

    def validate(self):
        ''' validates options are ok '''
        a_list = []
        valid = True
        for item in self._aircraft_definitions:
            item.error_status = None
            if item.key in a_list:
                item.error_status = f"Duplicate entry found {item.display_name}"
                valid = False
                continue
            a_list.append(item.key)
            if not item.mode:
                item.error_status = f"Mode not selected"
                valid = False
                continue
            if not item.mode in self._mode_list:
                item.error_status = f"Invalid mode {item.mode}"
                valid = False
                continue
            if not item.display_name:
                item.error_status = f"Aircraft name cannot be blank"
                valid = False

        return valid

    def find_definition_by_aicraft(self, aircraft) -> SimconnectAicraftDefinition:
        ''' gets an item by aircraft name (not case sensitive)'''
        if not aircraft:
            return None
        key = aircraft.lower().strip()
        item : SimconnectAicraftDefinition
        for item in self._aircraft_definitions:
            if item.key == key:
                return item
        return None
    
    def find_definition_by_title(self, title) -> SimconnectAicraftDefinition:
        ''' finds aircraft data by the loaded aircraft title '''
        if not title:
            return None
        for item in self._aircraft_definitions:
            if title in item.titles:
                return item
            
        return None
        

    
    @property
    def auto_mode_select(self):
        return self._auto_mode_select
    @auto_mode_select.setter
    def auto_mode_select(self, value):
        self._auto_mode_select = value
        


    def save(self):
        ''' saves the configuration data '''
        self.to_xml()

    def parse_xml(self):
        xml_source = self._xml_source
        if not os.path.isfile(xml_source):
            # options not saved yet - ignore
            return
        
    
        self._titles = []
        
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            root = etree.parse(xml_source, parser)

            nodes = root.xpath('//options')
            for node in nodes:
                if "auto_mode_select" in node.attrib:
                    self._auto_mode_select = safe_read(node,"auto_mode_select",bool,True)
                if "community_folder" in node.attrib:
                    self._community_folder = safe_read(node,"community_folder", str, "")
                if "sort" in node.attrib:
                    try:
                        sort_mode = safe_read(node,"sort",int, SimconnectSortMode.NotSet.value)
                        self._sort_mode = SimconnectSortMode(sort_mode)
                    except:
                        self._sort_mode = SimconnectSortMode.NotSet
                        pass
                break

            # reference items scanned from MSFS
            node_items = None
            nodes = root.xpath("//items")
            for node in nodes:
                node_items = node
                break

            if node_items is not None:
                for node in node_items:
                    icao_model = safe_read(node,"model", str, "")
                    icao_manufacturer = safe_read(node,"manufacturer", str, "")
                    icao_type = safe_read(node,"type", str, "")
                    path = safe_read(node,"path", str, "")
                    mode = safe_read(node,"mode", str, "")
                    id = safe_read(node,"id", str, "")
                    titles = []
                    node_titles = None
                    for child in node:
                        node_titles = child

                    if node_titles is not None:
                        for child in node_titles:
                            titles.append(child.text)

                    if icao_model and icao_manufacturer and icao_type:
                        item = SimconnectAicraftDefinition(id = id, 
                                                           icao_model = icao_model, 
                                                           icao_manufacturer = icao_manufacturer, 
                                                           icao_type = icao_type, 
                                                           titles = titles,
                                                           path = path,
                                                           mode = mode)
                        self._aircraft_definitions.append(item)

            node_titles = None
            nodes = root.xpath("//titles")
            for node in nodes:
                node_titles = node
                break
            
            if node_titles is not None:
                for node in node_titles:
                    if node.tag == "title":
                        title = node.text
                        if title:
                            self._titles.append(title)

            # sort the entries according to the current sort mode
            self.sort()


        except Exception as err:
            logging.getLogger("system").error(f"Simconnect Config: XML read error: {xml_source}: {err}")  
            return False

    def to_xml(self):
        # writes the configuration to xml

        root = etree.Element("simconnect_config")

        node_options = etree.SubElement(root, "options")
        # selection mode
        node_options.set("auto_mode_select",str(self._auto_mode_select))
        if self._community_folder and os.path.isdir(self._community_folder):
            # save valid community folder
            node_options.set("community_folder", self._community_folder)
        node_options.set("sort", str(self._sort_mode.value))

        # scanned aicraft titles 
        if self._aircraft_definitions:
            node_items = etree.SubElement(root,"items")
            for item in self._aircraft_definitions:
                node = etree.SubElement(node_items,"item")
                node.set("model", item.icao_model)
                node.set("manufacturer", item.icao_manufacturer)
                node.set("type",item.icao_type)
                node.set("path", item.path)
                node.set("id", item.id)
                node.set("mode", item.mode)
                if item.titles:
                    node_titles = etree.SubElement(node, "titles")
                    for title in item.titles:
                        child = etree.SubElement(node_titles, "title")
                        child.text = title
        
        try:
            # save the file
            tree = etree.ElementTree(root)
            tree.write(self._xml_source, pretty_print=True,xml_declaration=True,encoding="utf-8")
        except Exception as err:
            logging.getLogger("system").error(f"SimconnectData: unable to create XML simvars: {self._xml_source}: {err}")

    def get_community_folder(self):
        ''' community folder '''
        dir = QtWidgets.QFileDialog.getExistingDirectory(
            None,
            "Select Community Folder",
            dir = self.community_folder
        )
        if dir and os.path.isdir(dir):
            self.community_folder = dir
            return dir
        return None


    def scan_aircraft_config(self, owner):
        ''' scans MSFS folders for the list of aircraft names '''
        
        def fix_entry(value):
            if "\"" in value:
                # remove double quotes
                matches = re.findall('"(.*?)"', value)
                if matches:
                    value = matches.pop()
                # remove single quote
                matches = re.findall('(.*?)"', value)
                if matches:
                    value = matches.pop()

            # value = re.sub(r'[^0-9a-zA-Z\s_-]+', '', value)
            
            return value.strip()


        options = SimconnectOptions()

        from gremlin.ui import ui_common
        if not self._community_folder or not os.path.isdir(self._community_folder):
            self._community_folder = self.get_community_folder()
        if not self._community_folder or not os.path.isdir(self._community_folder):
            return
        #gremlin.util.pushCursor()

        progress = QtWidgets.QProgressDialog(parent = owner, labelText ="Scanning folders...", cancelButtonText = "Cancel", minimum = 0, maximum= 100) #, flags = QtCore.Qt.FramelessWindowHint)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setValue(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        search_folder = os.path.dirname(self._community_folder)
        source_files = gremlin.util.find_files(search_folder,"aircraft.cfg")

        
        cmp_icao_type =  r'(?i)icao_type_designator\s*=\s*\"?(.*?)\"?$'
        cmp_icao_manuf =  r'(?i)icao_manufacturer\s*=\s*\"?(.*?)\"?$'
        cmp_icao_model =  r'(?i)icao_model\s*=\s*\"?(.*?)\"?$'
        cmp_title = r"(?i)title\s*=\s*\"?(.*?)\"?$"
        file_count = len(source_files)

        progress.setLabelText = f"Processing {file_count:,} aircraft..."
        is_canceled = False
        items = []
        keys = []
        for count, file in enumerate(source_files):

            progress.setValue(int(100 * count / file_count))
            if progress.wasCanceled():
                is_canceled  = True
                break
            
            base_dir = os.path.dirname(file)
            cockpit_file = os.path.join(base_dir, "cockpit.cfg")
            if not os.path.isfile(cockpit_file):
                # not a player flyable airplane, skip
                continue

            titles = []
            icao_type = None
            icao_model = None
            icao_manuf = None

            with open(file,"r",encoding="utf8") as f:
                for line in f.readlines():
                    matches = re.findall(cmp_icao_type, line)
                    if matches:
                        icao_type = fix_entry(matches.pop())
                        continue
                    matches = re.findall(cmp_icao_manuf, line)
                    if matches:
                        icao_manuf = fix_entry(matches.pop())
                        continue
                    matches = re.findall(cmp_icao_model, line)
                    if matches:
                        icao_model = fix_entry(matches.pop())
                        continue

                    matches = re.findall(cmp_title, line)
                    if matches:
                        titles.extend(matches)
                        

            
            if titles:
                titles = list(set(titles))
                titles = [fix_entry(t) for t in titles]
                titles.sort()
            if icao_model and icao_type and icao_manuf:
                path = os.path.dirname(file)
                item = SimconnectAicraftDefinition(icao_type=icao_type,
                                                   icao_manufacturer= icao_manuf,
                                                   icao_model= icao_model,
                                                   titles= titles, 
                                                   path = path)
                if not item.display_name in keys:
                    # avoid duplicate entries
                    items.append(item)
                    keys.append(item.display_name)

        if not is_canceled:
            # update modes that exist already so they are preserved between scans
            mapped_modes = {}
            for item in self._aircraft_definitions:
                mapped_modes[item.display_name.lower()] = (item.id, item.mode)
            
            self._aircraft_definitions = items

            # sort 
            self.sort()
        
            for item in self._aircraft_definitions:
                display_name = item.display_name.lower()
                if display_name in mapped_modes.keys():
                    item.id, item.mode = mapped_modes[display_name]

        self.save()
        progress.close()
        
        #gremlin.util.popCursor()
        
    def sort(self):
        ''' sorts definitions '''
        if self._sort_mode == SimconnectSortMode.AicraftAscending:
            self._aircraft_definitions.sort(key = lambda x: x.key)
        elif self._sort_mode == SimconnectSortMode.AircraftDescending:
            self._aircraft_definitions.sort(key = lambda x: x.key, reverse = True)
        elif self._sort_mode == SimconnectSortMode.Mode:
            self._aircraft_definitions.sort(key = lambda x: (x.mode.lower(), x.key))



class ActionContainerUi(QtWidgets.QDialog):
    """UI to setup the individual action trigger containers and sub actions """

    def __init__(self, gate_data, index, is_range = False, parent=None):
        '''
        :param: gate_data = the gate data block 
        :item_data: the InputItem data block holding the container and input device configuration for this gated input
        :index: the gate number of the gated input - there will at least be two for low and high - index is an integer 
        '''
        
        super().__init__(parent)

        self._index = index
        self._gate_data = gate_data
        self._item_data = gate_data.item_data
        self._is_range = is_range

        # make modal
        self.setWindowModality(QtCore.Qt.ApplicationModal)

        min_min_sp = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Minimum
        )
        exp_min_sp = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.Minimum
        )        

        # Actual configuration object being managed
        self.setMinimumWidth(600)
        self.setMinimumWidth(800)


        self.action_widget = QtWidgets.QComboBox()
        self.condition_widget = QtWidgets.QComboBox()
        self.condition_description_widget = QtWidgets.QLabel()

        self.trigger_container_widget = QtWidgets.QWidget()
        self.trigger_condition_layout = QtWidgets.QHBoxLayout(self.trigger_container_widget)

        # actions = [GateAction.NoAction, GateAction.Gate]
        # for action in actions:
        #     self.action_widget.addItem(GateAction.to_display_name(action), action)
        # index = self.action_widget.findData(self._gate_data.getGateAction(self._index))
        # self.action_widget.setCurrentIndex(index)
        # self.action_widget.currentIndexChanged.connect(self._action_changed_cb)

        if is_range:
            self.trigger_condition_layout.addWidget(QtWidgets.QLabel(f"Range {index + 1} Configuration:"))
        else:
            self.trigger_condition_layout.addWidget(QtWidgets.QLabel(f"Gate {index + 1} Configuration:"))
        
        #self.trigger_condition_layout.addWidget(self.action_widget)
        self.trigger_condition_layout.addWidget(QtWidgets.QLabel(f"Condition:"))
        self.trigger_condition_layout.addWidget(self.condition_widget)
        self.trigger_condition_layout.addWidget(self.condition_description_widget)
        self.trigger_condition_layout.addStretch()

        from gremlin.ui.device_tab import InputItemConfiguration
        self.container_widget = InputItemConfiguration(self._item_data)
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.addWidget(self.trigger_container_widget)

        self.main_layout.addWidget(self.container_widget)   

        self._update_ui()

    # @QtCore.Slot()
    # def _action_changed_cb(self):
    #     self._gate_data.setGateAction(self._index, self.action_widget.currentData())
    #     self._update_ui()

    @QtCore.Slot()
    def _condition_changed_cb(self):
        self._gate_data.setGateCondition(self._index, self.condition_widget.currentData())

    def _update_ui(self):
        ''' updates controls based on the options '''
        conditions = self._gate_data.getGateValidConditions(self._index)
        with QtCore.QSignalBlocker(self.condition_widget):
            self.condition_widget.clear()
            for condition in conditions:
                self.condition_widget.addItem(GateCondition.to_display_name(condition), condition)
            condition = self._gate_data.getGateCondition(self._index)
            index = self.condition_widget.findData(condition)
            self.condition_widget.setCurrentIndex(index)
            self.condition_description_widget.setText(GateCondition.to_description(condition))



class SimconnectOptionsUi(QtWidgets.QDialog):
    """UI to set individual simconnect  settings """

    def __init__(self, parent=None):
        from gremlin.ui import ui_common
        super().__init__(parent)

        # make modal
        self.setWindowModality(QtCore.Qt.ApplicationModal)

        min_min_sp = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Minimum
        )
        exp_min_sp = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.Minimum
        )        

        # Actual configuration object being managed
        self.config = gremlin.config.Configuration()
        self.setMinimumWidth(600)


        self.mode_list = []
        self.profile : gremlin.base_profile.Profile = gremlin.shared_state.current_profile
        self.mode_list = self.profile.get_modes()
        self.default_mode = self.profile.get_default_mode()

        # display name to mode pair list
        self.mode_pair_list = gremlin.ui.ui_common.get_mode_list(self.profile)

        self.options = SimconnectOptions()

        self.setWindowTitle("Simconnect Options")

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self._auto_mode_switch = QtWidgets.QCheckBox("Change profile mode based on active aicraft")
        self._auto_mode_switch.setToolTip("When enabled, the profile mode will automatically change based on the mode associated with the active player aircraft in Flight Simulator")
        self._auto_mode_switch.setChecked(self.options.auto_mode_select)
        self._auto_mode_switch.clicked.connect(self._auto_mode_select_cb)

        self._msfs_path_widget = ui_common.QPathLineItem(header="MSFS Community Folder", text = self.options.community_folder, dir_mode=True)
        self._msfs_path_widget.pathChanged.connect(self._community_folder_changed_cb)
        self._msfs_path_widget.open.connect(self._community_folder_open_cb)

        self._mode_from_aircraft_button_widget = QtWidgets.QPushButton("Mode from Aicraft")
        self._mode_from_aircraft_button_widget.clicked.connect(self._mode_from_aircraft_button_cb)

        # toolbar for map
        self.container_bar_widget = QtWidgets.QWidget()
        self.container_bar_layout = QtWidgets.QHBoxLayout(self.container_bar_widget)
        self.container_bar_layout.setContentsMargins(0,0,0,0)


        self.edit_mode_widget = QtWidgets.QPushButton()
        self.edit_mode_widget.setIcon(gremlin.util.load_icon("manage_modes.svg"))
        self.edit_mode_widget.clicked.connect(self._manage_modes_cb)
        self.edit_mode_widget.setToolTip("Manage Modes")

        
        self.scan_aircraft_widget = QtWidgets.QPushButton("Scan Aircraft")
        self.scan_aircraft_widget.setIcon(gremlin.util.load_icon("mdi.magnify-scan"))
        self.scan_aircraft_widget.clicked.connect(self._scan_aircraft_cb)
        self.scan_aircraft_widget.setToolTip("Scan MSFS aicraft folders for aircraft names")

        
        self.container_bar_layout.addWidget(self.edit_mode_widget)
        self.container_bar_layout.addWidget(self.scan_aircraft_widget)
        self.container_bar_layout.addStretch()

        # start scrolling container widget definition

        self.container_map_widget = QtWidgets.QWidget()
        self.container_map_layout = QtWidgets.QVBoxLayout(self.container_map_widget)
        self.container_map_layout.setContentsMargins(0,0,0,0)

        # add aircraft map items
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout()

        # Configure the widget holding the layout with all the buttons
        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Configure the scroll area
        self.scroll_area.setMinimumWidth(300)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_widget)

        self.map_widget = QtWidgets.QWidget()
        self.map_layout = QtWidgets.QGridLayout(self.map_widget)
        self.map_layout.setContentsMargins(0,0,0,0)
        

        self.scroll_layout.addWidget(self.map_widget)
        self.scroll_layout.setContentsMargins(6,0,6,0)
        self.scroll_layout.addStretch()
        self.container_map_layout.addWidget(self.scroll_area)

        # end scrolling container widget definition

        
        self.close_button_widget = QtWidgets.QPushButton("Close")
        self.close_button_widget.clicked.connect(self.close_button_cb)


        button_bar_widget = QtWidgets.QWidget()
        button_bar_layout = QtWidgets.QHBoxLayout(button_bar_widget)
        button_bar_layout.addStretch()
        button_bar_layout.addWidget(self.close_button_widget)


        self.main_layout.addWidget(self._auto_mode_switch)
        self.main_layout.addWidget(self._msfs_path_widget)
        self.main_layout.addWidget(self.container_bar_widget)
        self.main_layout.addWidget(self.container_map_widget)
        self.main_layout.addWidget(button_bar_widget)


        
        self._populate_ui()

    @QtCore.Slot()
    def _manage_modes_cb(self):
        import gremlin.shared_state
        gremlin.shared_state.ui.manage_modes()
        self._populate_ui()

    @QtCore.Slot(object)
    def _community_folder_open_cb(self, widget):
        ''' opens the profile list '''
        dir = self.options.get_community_folder()
        if dir:
            with QtCore.QSignalBlocker(widget):
                widget.setText(dir)

    @QtCore.Slot(object, str)
    def _community_folder_changed_cb(self, widget, text):
        if os.path.isdir(text):
            self.options.community_folder = text

    def closeEvent(self, event):
        ''' occurs on window close '''
        self.options.save()
        super().closeEvent(event)

    @QtCore.Slot(bool)
    def _auto_mode_select_cb(self, checked):
        ''' auto mode changed'''
        self.options.auto_mode_select = checked

    @QtCore.Slot()
    def _scan_aircraft_cb(self):
        self.options.scan_aircraft_config(self)

        # update the aicraft drop down choices
        self._populate_ui()





    @QtCore.Slot()
    def close_button_cb(self):
        ''' called when close button clicked '''
        self.close()

    

    def _populate_ui(self):
        ''' populates the map of aircraft to profile modes '''

        from gremlin.ui import ui_common
        self.options.validate()


        # figure out the size of the header part of the control so things line up
        lbl = QtWidgets.QLabel("w")
        char_width = lbl.fontMetrics().averageCharWidth()
        headers = ["Aicraft:"]
        width = 0
        for header in headers:
            width = max(width, char_width*(len(header)))


        # clear the widgets
        ui_common.clear_layout(self.map_layout)

        # display one row per aicraft found
        if not self.options._aircraft_definitions:
             missing = QtWidgets.QLabel("No mappings found.")
             missing.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
             self.map_layout.addWidget(missing)
             return

        gremlin.util.pushCursor()

        item : SimconnectAicraftDefinition

        self._mode_selector_map = {}
        self._selected_cb_map = {}
        row = 0
        display_width = width
        for item in self.options._aircraft_definitions:

            # header row
            if row == 0:
      
                select_widget = QtWidgets.QCheckBox()
                select_widget.clicked.connect(self._global_selected_changed_cb)
                select_widget.setToolTip("Select/Deselect All")

                aircraft_header_widget = QtWidgets.QWidget()
                aircraft_header_layout = QtWidgets.QHBoxLayout(aircraft_header_widget)

                self.display_header_widget = QtWidgets.QLabel("Aicraft")
                aircraft_header_layout.addWidget(self.display_header_widget)
                display_sort_up_widget = QtWidgets.QPushButton()
                display_sort_up_widget.setIcon(gremlin.util.load_icon("fa.sort-asc"))
                display_sort_up_widget.setMaximumWidth(20)
                display_sort_up_widget.clicked.connect(self._sort_display_up_cb)
                display_sort_up_widget.setStyleSheet("border: none;")
                display_sort_up_widget.setToolTip("Sort aircraft ascending")

                display_sort_down_widget = QtWidgets.QPushButton()
                display_sort_down_widget.setIcon(gremlin.util.load_icon("fa.sort-desc"))
                display_sort_down_widget.setMaximumWidth(20)
                display_sort_down_widget.clicked.connect(self._sort_display_down_cb)
                display_sort_down_widget.setStyleSheet("border: none;")
                display_sort_down_widget.setToolTip("Sort aircraft descending")

                aircraft_header_layout.addStretch()
                aircraft_header_layout.addWidget(display_sort_up_widget)
                aircraft_header_layout.addWidget(display_sort_down_widget)

                mode_header_widget = QtWidgets.QWidget()
                mode_header_layout = QtWidgets.QHBoxLayout(mode_header_widget)

                mode_sort_up_widget = QtWidgets.QPushButton()
                mode_sort_up_widget.setIcon(gremlin.util.load_icon("fa.sort-asc"))
                mode_sort_up_widget.setMaximumWidth(20)
                mode_sort_up_widget.clicked.connect(self._sort_mode_up_cb)
                mode_sort_up_widget.setStyleSheet("border: none;")
                mode_sort_up_widget.setToolTip("Sort by mode")


                mode_widget = QtWidgets.QLabel("Mode")
                mode_header_layout.addWidget(mode_widget)
                mode_header_layout.addStretch()
                mode_header_layout.addWidget(mode_sort_up_widget)
                




                manufacturer_widget = QtWidgets.QLabel("Manufacturer")

                type_widget = QtWidgets.QLabel("Type")
                model_widget = QtWidgets.QLabel("Model")


                row_selector = ui_common.QRowSelectorFrame()
                row_selector.setSelectable(False)
                spacer = ui_common.QDataWidget()
                spacer.setMinimumWidth(3)
                self.map_layout.addWidget(row_selector, 0, 0, 1, -1)
                
                self.map_layout.addWidget(spacer, 0, 1)
                self.map_layout.addWidget(select_widget, 0, 2)
                self.map_layout.addWidget(aircraft_header_widget, 0, 3)
                self.map_layout.addWidget(mode_header_widget, 0, 4)
                self.map_layout.addWidget(manufacturer_widget, 0, 5)
                self.map_layout.addWidget(model_widget, 0, 6)
                self.map_layout.addWidget(type_widget, 0, 7)

                

               

                row+=1
                continue

            
             # selector
            row_selector = ui_common.QRowSelectorFrame(selected = item.selected)
            row_selector.setMinimumHeight(30)
            row_selector.selected_changed.connect(self._row_selector_clicked_cb)
            selected_widget = ui_common.QDataCheckbox(data = (item, row_selector))
            selected_widget.setChecked(item.selected)
            selected_widget.checkStateChanged.connect(self._selected_changed_cb)
            row_selector.data = ((item, selected_widget))

            # aicraft display 
            self.display_header_widget = ui_common.QDataLineEdit(data = (item, selected_widget))
            self.display_header_widget.setReadOnly(True)
            self.display_header_widget.setText(item.display_name)
            self.display_header_widget.installEventFilter(self)
            w = len(item.display_name)*char_width
            if w > display_width:
                display_width = w

            # manufacturer
            manufacturer_widget = ui_common.QDataLineEdit(data = (item, selected_widget))
            manufacturer_widget.setReadOnly(True)
            manufacturer_widget.setText(item.icao_manufacturer)
            manufacturer_widget.installEventFilter(self)

            # model
            model_widget = ui_common.QDataLineEdit(data = (item, selected_widget))
            model_widget.setReadOnly(True)
            model_widget.setText(item.icao_model)
            model_widget.installEventFilter(self)

            # type
            type_widget = ui_common.QDataLineEdit(data = (item, selected_widget))
            type_widget.setReadOnly(True)
            type_widget.setText(item.icao_type)
            type_widget.installEventFilter(self)

       

            # mode drop down
            mode_selector = ui_common.QDataComboBox(data = (item, selected_widget))
            for display_mode, mode in self.mode_pair_list:
                mode_selector.addItem(display_mode, mode)
            if not item.mode:
                item.mode = self.default_mode
            if not item.mode in self.mode_list:
                item.mode = self.default_mode
            index = mode_selector.findData(item.mode)
            mode_selector.setCurrentIndex(index)
            mode_selector.currentIndexChanged.connect(self._mode_selector_changed_cb)
            self._mode_selector_map[item] = mode_selector
            self._selected_cb_map[item] = selected_widget

            self.map_layout.addWidget(row_selector, row ,0 , 1, -1)
            
            spacer = ui_common.QDataWidget()
            spacer.setMinimumWidth(3)
            spacer.installEventFilter(self)
            
            self.map_layout.addWidget(spacer, row, 1)
            self.map_layout.addWidget(selected_widget, row, 2)
            self.map_layout.addWidget(self.display_header_widget, row, 3 )
            self.map_layout.addWidget(mode_selector, row, 4 )
            self.map_layout.addWidget(manufacturer_widget,row, 5 )
            self.map_layout.addWidget(model_widget,row, 6)
            self.map_layout.addWidget(type_widget,row, 7)
            spacer = ui_common.QDataWidget()
            spacer.installEventFilter(self)
            spacer.setMinimumWidth(6)
            self.map_layout.addWidget(spacer, row, 8)


            row += 1


        self.map_layout.setColumnStretch(3,2)
        self.map_layout.setColumnMinimumWidth(3, display_width)


        gremlin.util.popCursor()


    @QtCore.Slot()
    def _sort_display_up_cb(self):
        # sorts data by aicraft name 
        self.options._sort_mode = SimconnectSortMode.AicraftAscending
        self.options.sort()
        self._populate_ui()
        self.scroll_area.ensureVisible(0,0)
        
    @QtCore.Slot()
    def _sort_display_down_cb(self):
        # sorts data by aicraft name reversed
        self.options._sort_mode = SimconnectSortMode.AircraftDescending
        self.options.sort()
        self._populate_ui()
        self.scroll_area.ensureVisible(0,0)

    @QtCore.Slot()
    def _sort_mode_up_cb(self):
        # sorts data by mode        
        self.options._sort_mode = SimconnectSortMode.Mode
        self.options.sort()
        self._populate_ui()
        self.scroll_area.ensureVisible(0,0)        
        
        

    
        
        

    @QtCore.Slot(bool)
    def _global_selected_changed_cb(self, checked):
        for item in self._selected_cb_map.keys():
            self._selected_cb_map[item].setChecked(checked)


    def _get_selected(self):
        ''' gets the items that are selected '''
        return [item for item in self.options._aircraft_definitions if item.selected]


    @QtCore.Slot(bool)
    def _selected_changed_cb(self, state):
        widget = self.sender()
        item, row_selector = widget.data
        checked = widget.isChecked() # param is an enum - ignore
        item.selected = checked
        row_selector.selected = checked

    @QtCore.Slot()
    def _row_selector_clicked_cb(self):
        widget = self.sender()
        checked = widget.selected
        item, selector_widget = widget.data
        item.selected = checked
        with QtCore.QSignalBlocker(selector_widget):
            selector_widget.setChecked(checked)

            

    def eventFilter(self, widget, event):
        ''' ensure line changes are saved '''
        t = event.type()
        if t == QtCore.QEvent.Type.MouseButtonPress:
            item, selected_widget = widget.data
            selected_widget.setChecked(not selected_widget.isChecked())


        return False


    @QtCore.Slot(int)
    def _mode_selector_changed_cb(self, selected_index):
        ''' occurs when the mode is changed on an entry '''
        widget = self.sender()
        mode = widget.currentData()
        item, _ = widget.data
        items = self._get_selected()
        if not item in items:
            items.append(item)
        mode_index = None
        for item in items:
            if item.mode != mode:
                item.mode = mode
                selector = self._mode_selector_map[item]
                with QtCore.QSignalBlocker(selector):
                    if mode_index is None:
                        mode_index = selector.findData(mode)
                    selector.setCurrentIndex(mode_index)

    @QtCore.Slot()
    def _active_button_cb(self):
        widget = self.sender()
        sm = SimConnectData()
        
        aircraft = sm.get_aircraft()
        if aircraft:
            item = widget.data
            item.aircraft = aircraft

        
    @QtCore.Slot()
    def _mode_from_aircraft_button_cb(self):
        ''' mode from aicraft button '''
        aircraft, model, title = self._sm_data.get_aircraft_data()
        logging.getLogger("system").info(f"Aircraft: {aircraft} model: {model} title: {title}")
        if not title in self._mode_list:
            self.profile.add_mode(title)
            



            





class MapToSimConnectWidget(gremlin.ui.input_item.AbstractActionWidget):

    """UI widget for mapping inputs to keyboard key combinations - adds extra functionality to the base module ."""

    def __init__(self, action_data, parent=None):
        """Creates a new instance.

        :param action_data the data managed by this widget
        :param parent the parent of this widget
        """
        
        self.action_data : MapToSimConnect = action_data
        self.block = None
        self._sm_data = SimConnectData()
        self.options = SimconnectOptions()

        # call super last because it will call create_ui and populate_ui so the vars must exist
        super().__init__(action_data, parent=parent)

    def _create_ui(self):
        """Creates the UI components."""
        import gremlin.gated_handler
        # mode from aircraft button - grabs the aicraft name as a mode
        # policy = self.sizePolicy()
        # policy.setVerticalPolicy(QtWidgets.QSizePolicy.Policy.Expanding)
        self._options_button_widget = QtWidgets.QPushButton("Simconnect Options")
        self._options_button_widget.setIcon(gremlin.util.load_icon("fa.gear"))
        self._options_button_widget.clicked.connect(self._show_options_dialog_cb)
        
        # self._toolbar_container_widget = QtWidgets.QWidget()
        # self._toolbar_container_layout = QtWidgets.QHBoxLayout(self._toolbar_container_widget)
        # self._toolbar_container_layout.addWidget(self._options_button_widget)
        # self._toolbar_container_layout.addStretch()

        # command selector
        self._command_container_widget = QtWidgets.QWidget()
        self._command_container_layout = QtWidgets.QVBoxLayout(self._command_container_widget)

        


        self._action_selector_widget = QtWidgets.QWidget()
        self._action_selector_layout = QtWidgets.QHBoxLayout(self._action_selector_widget)

        # list of possible events to trigger
        self._command_selector_widget = QtWidgets.QComboBox()
        self._command_list = self._sm_data.get_command_name_list()
        self._command_selector_widget.setEditable(True)
        self._command_selector_widget.addItems(self._command_list)
        self._command_selector_widget.currentIndexChanged.connect(self._command_changed_cb)

        self._command_selector_widget.setValidator(CommandValidator())

        # setup auto-completer for the command 
        command_completer = QtWidgets.QCompleter(self._command_list, self)
        command_completer.setCaseSensitivity(QtGui.Qt.CaseSensitivity.CaseInsensitive)

        self._command_selector_widget.setCompleter(command_completer)

        #self.action_selector_layout.addWidget(self.category_widget)
        self._action_selector_layout.addWidget(QtWidgets.QLabel("Selected command:"))
        self._action_selector_layout.addWidget(self._command_selector_widget)
        self._action_selector_layout.addStretch()
        self._action_selector_layout.addWidget(self._options_button_widget)
        self._action_selector_widget.setContentsMargins(0,0,0,0)
        

        self._output_mode_widget = QtWidgets.QWidget()
        self._output_mode_layout = QtWidgets.QHBoxLayout(self._output_mode_widget)
        self._output_mode_widget.setContentsMargins(0,0,0,0)
        
        self._output_mode_readonly_widget = QtWidgets.QRadioButton("Read/Only")
        self._output_mode_readonly_widget.setEnabled(False)

        # set range of values output mode (axis input only)
        self._output_mode_ranged_widget = QtWidgets.QRadioButton("Ranged")
        self._output_mode_ranged_widget.clicked.connect(self._mode_ranged_cb)

        self._output_mode_gated_widget =  QtWidgets.QRadioButton("Gated")
        self._output_mode_gated_widget.clicked.connect(self._mode_gated_cb)


        # trigger output mode (event trigger only)
        self._output_mode_trigger_widget = QtWidgets.QRadioButton("Trigger")
        self._output_mode_trigger_widget.clicked.connect(self._mode_trigger_cb)

        self._output_mode_description_widget = QtWidgets.QLabel()
        self._output_mode_layout.addWidget(QtWidgets.QLabel("Output mode:"))


        # set value output mode (output value only)
        self._output_mode_set_value_widget = QtWidgets.QRadioButton("Value")
        self._output_mode_set_value_widget.clicked.connect(self._mode_value_cb)

        self._output_mode_layout.addWidget(self._output_mode_readonly_widget)
        self._output_mode_layout.addWidget(self._output_mode_trigger_widget)
        self._output_mode_layout.addWidget(self._output_mode_set_value_widget)
        self._output_mode_layout.addWidget(self._output_mode_ranged_widget)
        self._output_mode_layout.addWidget(self._output_mode_gated_widget)
        self._output_mode_layout.addStretch()

        self.output_readonly_status_widget = QtWidgets.QLabel("Read only")
        self._output_mode_layout.addWidget(self.output_readonly_status_widget)

        self._output_invert_axis_widget = QtWidgets.QCheckBox("Invert axis")
        self._output_invert_axis_widget.setChecked(self.action_data.invert_axis)
        self._output_invert_axis_widget.clicked.connect(self._output_invert_axis_cb)




        # output data type UI 
        self._output_data_type_widget = QtWidgets.QWidget()
        self._output_data_type_layout = QtWidgets.QHBoxLayout(self._output_data_type_widget)
        
        self._output_data_type_label_widget = QtWidgets.QLabel("Not Set")

        # self._output_block_type_description_widget = QtWidgets.QLabel()

        self._output_data_type_layout.addWidget(QtWidgets.QLabel("Output type:"))
        self._output_data_type_layout.addWidget(self._output_data_type_label_widget)
        self._output_data_type_layout.addWidget(self._output_mode_description_widget)
        self._output_data_type_layout.addStretch()
        self._output_data_type_widget.setContentsMargins(0,0,0,0)


        # output range UI
        self._output_range_container_widget = QtWidgets.QWidget()
        self._output_range_container_layout = QtWidgets.QVBoxLayout(self._output_range_container_widget)
        self._output_range_container_widget.setContentsMargins(0,0,0,0)
        

        self._output_range_ref_text_widget = QtWidgets.QLabel()
        self._output_range_container_layout.addWidget(self._output_range_ref_text_widget)

        output_row_widget = QtWidgets.QWidget()
        output_row_layout = QtWidgets.QHBoxLayout(output_row_widget)
                
        self._output_min_range_widget = QtWidgets.QSpinBox()
        self._output_min_range_widget.setRange(-16383,16383)
        self._output_min_range_widget.valueChanged.connect(self._min_range_changed_cb)

        self._output_max_range_widget = QtWidgets.QSpinBox()
        self._output_max_range_widget.setRange(-16383,16383)
        self._output_max_range_widget.valueChanged.connect(self._max_range_changed_cb)
        output_row_layout.addWidget(self._output_invert_axis_widget)
        output_row_layout.addWidget(QtWidgets.QLabel("Range min:"))
        output_row_layout.addWidget(self._output_min_range_widget)
        output_row_layout.addWidget(QtWidgets.QLabel("Range max:"))
        output_row_layout.addWidget(self._output_max_range_widget)
        output_row_layout.addStretch(1)
        

        self._output_range_container_layout.addWidget(output_row_widget)

        # holds the output value if the output value is a fixed value
        self._output_value_container_widget = QtWidgets.QWidget()
        self._output_value_container_layout = QtWidgets.QHBoxLayout(self._output_value_container_widget)
        self._output_value_container_widget.setContentsMargins(0,0,0,0)
        self._output_value_widget = gremlin.ui.ui_common.DynamicDoubleSpinBox()
        self._output_value_widget.valueChanged.connect(self._output_value_changed_cb)
        self._output_value_description_widget = QtWidgets.QLabel()

        # holds the gated axis container
        self._output_gated_container_widget = QtWidgets.QWidget()
        self._output_gated_container_layout = QtWidgets.QVBoxLayout(self._output_gated_container_widget)
        self._output_gated_container_widget.setContentsMargins(0,0,0,0)
        
        self.command_header_container_widget = QtWidgets.QWidget()
        self.command_header_container_layout = QtWidgets.QHBoxLayout(self.command_header_container_widget)
        

        self.command_text_widget = QtWidgets.QLabel()
        self.command_header_container_layout.addWidget(QtWidgets.QLabel("<b>Command:</b>"))
        self.command_header_container_layout.addWidget(self.command_text_widget)


        self.description_text_widget = QtWidgets.QLabel()
        self.command_header_container_layout.addWidget(QtWidgets.QLabel("<b>Description</b>"))
        self.command_header_container_layout.addWidget(self.description_text_widget)
        self.command_header_container_layout.setContentsMargins(0,0,0,0)
        self.command_header_container_layout.addStretch(1)


        self._output_value_container_layout.addWidget(QtWidgets.QLabel("Output value:"))
        self._output_value_container_layout.addWidget(self._output_value_widget)
        self._output_value_container_layout.addWidget(self._output_value_description_widget)
        self._output_value_container_layout.addStretch(1)
        self._output_value_container_widget.setContentsMargins(0,0,0,0)

        # trigger mode (sends the command )
        self._output_trigger_container_widget = QtWidgets.QWidget()
        self._output_trigger_container_layout = QtWidgets.QHBoxLayout()
        self._output_trigger_container_widget.setLayout(self._output_trigger_container_layout)
        self._output_trigger_container_widget.setContentsMargins(0,0,0,0)
                


        # output options container - shows below selector - visible when a command is selected and changes with the active mode
        self._output_container_widget = QtWidgets.QWidget()
        self._output_container_layout = QtWidgets.QVBoxLayout(self._output_container_widget)
        self._output_container_widget.setContentsMargins(0,0,0,0)
        self._output_container_layout.addWidget(self.command_header_container_widget)
        self._output_container_layout.addWidget(QHLine())
        self._output_container_layout.addWidget(self._output_mode_widget)                
        self._output_container_layout.addWidget(self._output_data_type_widget)
        self._output_container_layout.addWidget(self._output_range_container_widget)
        self._output_container_layout.addWidget(self._output_value_container_widget)
        self._output_container_layout.addWidget(self._output_trigger_container_widget)
        self._output_container_layout.addWidget(self._output_gated_container_widget)
        self._output_container_layout.addStretch(1)



        self._gates_widget = gremlin.gated_handler.GatedAxisWidget(action_data = self.action_data)
        self._gates_widget.configure_requested.connect(self._configure_trigger_cb)
        self._gates_widget.configure_handle_requested.connect(self._configure_handle_trigger_cb)
        self._gates_widget.configure_range_requested.connect(self._configure_range_trigger_cb)
        self._output_gated_container_layout.addWidget(self._gates_widget)
        self._output_gated_container_widget.setMinimumHeight(min(200, self._gates_widget.gate_count * 200))
    

        # status widget
        self.status_text_widget = QtWidgets.QLabel()

        
        self._command_container_layout.addWidget(self._action_selector_widget)


        # hide output layout by default until we have a valid command
        self._output_container_widget.setVisible(False)

        #self.main_layout.addWidget(self._toolbar_container_widget)
        self.main_layout.addWidget(self._command_container_widget)
        self.main_layout.addWidget(self._output_container_widget)
        # self.main_layout.addWidget(self._input_container_widget)
        self.main_layout.addWidget(self.status_text_widget)

        #self.main_layout.addStretch(1)

        # # hook the joystick input for axis input repeater
        # el = gremlin.event_handler.EventListener()
        # el.joystick_event.connect(self._joystick_event_cb)


    QtCore.Slot(object)
    def _configure_trigger_cb(self, data):
        self._handle_clicked_cb(data, 0)

    

    QtCore.Slot(object, int)
    def _configure_handle_trigger_cb(self, data, index):
        dialog = ActionContainerUi(data, index)
        dialog.exec()


    QtCore.Slot(object, int)
    def _configure_range_trigger_cb(self, data, index):
        dialog = ActionContainerUi(data, index)
        dialog.exec()

    def _show_options_dialog_cb(self):
        ''' displays the simconnect options dialog'''
        dialog = SimconnectOptionsUi()
        dialog.exec()

    # @QtCore.Slot(object)
    # def _joystick_event_cb(self, event):
    #     if self.is_running or not event.is_axis:
    #         # ignore if not an axis event and if the profile is running, or input for a different device
    #         return
        
    #     if self.action_data.hardware_device_guid != event.device_guid:
    #         # print (f"device mis-match: {str(self.action_data.hardware_device_guid)}  {str(event.device_guid)}")
    #         return
            
    #     if self.action_data.hardware_input_id != event.identifier:
    #         # print (f"input mismatch: {self.action_data.hardware_input_id} {event.identifier}")
    #         return
        
    #     # axis value
    #     #if self.action_data.mode == SimConnectActionMode.Ranged:
    #     # ranged mode
    #     raw_value = event.raw_value
    #     input_value = gremlin.util.scale_to_range(raw_value, source_min = -32767, source_max = 32767, target_min = -1, target_max = 1) + 0 # removes negative zero in python
    #     self._input_axis_widget.setValue(input_value)
    #     output_value = gremlin.util.scale_to_range(input_value, target_min = self.action_data.min_range, target_max = self.action_data.max_range, invert= self.action_data.invert_axis) 
    #     self._output_axis_widget.setValue(output_value)
    #     self._input_axis_value_widget.setText(f"{input_value:0.2f}")
    #     self._output_axis_value_widget.setText(f"{output_value:0.2f}")








    def _output_value_changed_cb(self):
        ''' occurs when the output value has changed '''
        value = self._output_value_widget.value()
        block: SimConnectBlock
        block = self.block
        if block:
            block.disable_notifications()
            block.value = value
            block.enable_notifications()
            # store to profile
            self.action_data.value = value


    def _min_range_changed_cb(self):
        value = self._output_min_range_widget.value()
        block: SimConnectBlock
        block = self.block
        if block:
            block.disable_notifications()
            block.min_range_custom = value
            block.enable_notifications()
            # store to profile
            self.action_data.min_range = value
            self._output_axis_widget.setMinimum(value)

    def _max_range_changed_cb(self):
        value = self._output_max_range_widget.value()
        block: SimConnectBlock
        block = self.block
        if block:
            block.disable_notifications()
            block.max_range_custom = value
            block.enable_notifications()
            # store to profile
            self.action_data.max_range = value
            self._output_axis_widget.setMaximum(value)

    @QtCore.Slot(bool)
    def _output_invert_axis_cb(self, checked):
        self.action_data.invert_axis = checked
        

    def _command_changed_cb(self, index):
        ''' called when selected command changes '''
        command = self._command_selector_widget.currentText()
        
        block = self._sm_data.block(command)
        self._update_block_ui(block)

        # store command to profile
        self.action_data.command = command

    def _update_block_ui(self, block : SimConnectBlock):
        ''' updates the UI with a data block '''
        if self.block and self.block != block:
            # unhook block events
            self.block.range_changed.disconnect(self._range_changed_cb)

        self.block = block

        input_type = self.action_data.get_input_type()
        
        input_desc = ""
        if input_type == InputType.JoystickAxis:
            input_desc = "axis"
        elif input_type in (InputType.JoystickButton, InputType.VirtualButton):
            input_desc = "button"
        elif input_type == InputType.JoystickHat:
            input_desc = "hat"
        elif input_type in (InputType.Keyboard, InputType.KeyboardLatched):
            input_desc = "key"
        elif input_type in (InputType.Midi, InputType.OpenSoundControl):
            input_desc = "button or slider"



        if self.action_data.mode == SimConnectActionMode.Ranged:
            desc = f"Maps an input {input_desc} to a SimConnect ranged event, such as an axis"
        elif self.action_data.mode == SimConnectActionMode.Trigger:
            desc = f"Maps an input {input_desc} to a SimConnect triggered event, such as an on/off or toggle function."
        elif self.action_data.mode == SimConnectActionMode.SetValue:
            desc = f"Maps an input {input_desc} to a Simconnect event and sends it the specified value."
        elif self.action_data.mode == SimConnectActionMode.Gated:
            desc = f"Maps a gated input {input_desc} to a Simconnect event and sends it the specified value."
        else:
            desc = ""

        self._output_mode_description_widget.setText(desc)

        
        if block and block.valid:
            self._output_container_widget.setVisible(True)


            self.output_readonly_status_widget.setText("Block: read/only" if block.is_readonly else "Block: read/write")

            self.status_text_widget.setText("Command selected")

            if input_type == InputType.JoystickAxis:
                # input drives the outputs
                self._output_value_widget.setVisible(False)
            else:
                # button or event intput
                self._output_value_widget.setVisible(block.is_value)

            # display range information if the command is a ranged command
            self._output_range_container_widget.setVisible(block.is_ranged)

            # hook block events
            block.range_changed.connect(self._range_changed_cb)   

            # command description
            self.command_text_widget.setText(block.command)
            self.description_text_widget.setText(block.description)

            # update UI based on block information ``
            self._output_data_type_label_widget.setText(block.display_block_type)

            output_mode_enabled = not block.is_readonly

            if self.action_data.mode == SimConnectActionMode.NotSet:
                # come up with a default mode for the selected command if not set
                if input_type == InputType.JoystickAxis:
                    self.action_data.mode = SimConnectActionMode.Ranged
                else:
                    if block.is_value:
                        self.action_data.mode = SimConnectActionMode.SetValue
                    else:    
                        self.action_data.mode = SimConnectActionMode.Trigger            

            if not output_mode_enabled:
                self._output_mode_readonly_widget.setChecked(True)
                self.action_data.mode = SimConnectActionMode.NotSet
            elif self._output_mode_readonly_widget.isChecked():
                if input_type == InputType.JoystickAxis:
                    self.action_data.mode = SimConnectActionMode.Ranged
                elif block.is_value:
                    self.action_data.mode = SimConnectActionMode.SetValue
        
            self._output_mode_ranged_widget.setEnabled(output_mode_enabled)
            self._output_mode_set_value_widget.setEnabled(output_mode_enabled)
            self._output_mode_trigger_widget.setEnabled(output_mode_enabled)

            # intial state of mode radio buttons
                
            if self.action_data.mode == SimConnectActionMode.Trigger:
                with QtCore.QSignalBlocker(self._output_mode_trigger_widget):
                    self._output_mode_trigger_widget.setChecked(True)
            elif self.action_data.mode == SimConnectActionMode.SetValue:
                with QtCore.QSignalBlocker(self._output_mode_set_value_widget):
                    self._output_mode_set_value_widget.setChecked(True)
            elif self.action_data.mode == SimConnectActionMode.Ranged:
                with QtCore.QSignalBlocker(self._output_mode_ranged_widget):
                    self._output_mode_ranged_widget.setChecked(True)
            elif self.action_data.mode == SimConnectActionMode.Gated:
                with QtCore.QSignalBlocker(self._output_mode_gated_widget):
                    self._output_mode_gated_widget.setChecked(True)
            
            self._output_data_type_label_widget.setText(block.display_data_type)
            self.output_readonly_status_widget.setText("(command is Read/Only)" if block.is_readonly else '')

            is_ranged = block.is_ranged
            if is_ranged:
                self._output_range_ref_text_widget.setText(f"Command output range: {block.min_range:+}/{block.max_range:+}")
                if self.action_data.min_range < block.min_range:
                    self.action_data.min_range = block.min_range
                if self.action_data.max_range > block.max_range:
                    self.action_data.max_range = block.max_range
                if self.action_data.max_range > self.action_data.min_range:
                    self.action_data.max_range = block.max_range
                if self.action_data.min_range > self.action_data.min_range:
                    self.action_data.min_range = block.min_range

                with QtCore.QSignalBlocker(self._output_min_range_widget):
                    self._output_min_range_widget.setValue(self.action_data.min_range)  
                with QtCore.QSignalBlocker(self._output_max_range_widget):
                    self._output_max_range_widget.setValue(self.action_data.max_range)  

                # update the output data type
            if block.output_data_type == SimConnectBlock.OutputType.FloatNumber:
                self._output_data_type_label_widget.setText("Number (float)")
            elif block.output_data_type == SimConnectBlock.OutputType.IntNumber:
                self._output_data_type_label_widget.setText("Number (int)")
            else:
                self._output_data_type_label_widget.setText("N/A")



            return
        
        # clear the data
        self._output_container_widget.setVisible(False)
        self.status_text_widget.setText("Please select a command")


    def _update_ui(self):
        ''' updates the UI based on the output mode selected '''
        range_visible = self.action_data.mode == SimConnectActionMode.Ranged
        trigger_visible = self.action_data.mode == SimConnectActionMode.Trigger
        setvalue_visible = self.action_data.mode == SimConnectActionMode.SetValue
        gated_visible = self.action_data.mode == SimConnectActionMode.Gated
        
        self._output_range_container_widget.setVisible(range_visible)
        self._output_trigger_container_widget.setVisible(trigger_visible)
        self._output_value_container_widget.setVisible(setvalue_visible)
        self._output_gated_container_widget.setVisible(gated_visible)

    def _range_changed_cb(self, event : SimConnectBlock.RangeEvent):
        ''' called when range information changes on the current simconnect command block '''
        self._output_min_range_widget.setValue(event.min)
        self._output_max_range_widget.setValue(event.max)
        self._output_min_range_widget.setValue(event.min_custom)
        self._output_max_range_widget.setValue(event.max_custom)

    def _mode_ranged_cb(self):
        value = self._output_mode_ranged_widget.isChecked()
        if value:
            self.action_data.mode = SimConnectActionMode.Ranged
            self._update_ui()

    def _mode_gated_cb(self):
        value = self._output_mode_gated_widget.isChecked()
        if value:
            self.action_data.mode = SimConnectActionMode.Gated
            self._update_ui()

    def _mode_value_cb(self):
        value = self._output_mode_set_value_widget.isChecked()
        if value:
            self.action_data.mode = SimConnectActionMode.SetValue
            self._update_ui()
        
    def _mode_trigger_cb(self):
        value = self._output_mode_trigger_widget.isChecked()
        if value:
            self.action_data.mode = SimConnectActionMode.Trigger
            self._update_ui()

    def _readonly_cb(self):
        block : SimConnectBlock
        block = self.block
        
        readonly = block is not None and block.is_readonly
        checked = self.output_readonly_status_widget.isChecked() 
        if readonly != checked:
            with QtCore.QSignalBlocker(self.output_readonly_status_widget):
                self.output_readonly_status_widget.setChecked(readonly)
        
        self.action_data.is_readonly = readonly

    def _populate_ui(self):
        """Populates the UI components."""
        
        command = self._command_selector_widget.currentText()

        if self.action_data.command != command:
            with QtCore.QSignalBlocker(self._command_selector_widget):
                index = self._command_selector_widget.findText(self.action_data.command)
                self._command_selector_widget.setCurrentIndex(index)

        self.block = self._sm_data.block(self.action_data.command)
        self._update_block_ui(self.block)
        self._update_ui()




class MapToSimConnectFunctor(gremlin.base_profile.AbstractContainerActionFunctor):

    manager = gremlin.macro.MacroManager()

    def __init__(self, action):
        super().__init__(action)
        self.action_data : MapToSimConnect = action
        self.command = action.command # the command to execute
        self.value = action.value # the value to send (None if no data to send)
        self.sm = SimConnectData()
        self.block = self.sm.block(self.command)
    
    def profile_start(self):
        ''' occurs when the profile starts '''
        self.sm.connect()
        

    def profile_stop(self):
        ''' occurs wen the profile stops'''
        self.sm.disconnect()





                
    

    def scale_output(self, value):
        ''' scales an output value for the output range '''
        return gremlin.util.scale_to_range(value, target_min = self.action_data.min_range, target_max = self.action_data.max_range, invert=self.action_data.invert_axis) 

    def process_event(self, event, value):


        logging.getLogger("system").info(f"SC FUNCTOR: {event}  {value}")

        # execute the functors
        result = super().process_event(event, value)
        if not result:
            return True

        if not self.sm.ok:
            return True

        if not self.block or not self.block.valid:
            # invalid command
            return True
   
        if event.is_axis and self.block.is_axis:
            # value is a ranged input value
            if self.action_data.mode == SimConnectActionMode.Ranged:
                # come up with a default mode for the selected command if not set
                target = value.current
                output_value = gremlin.util.scale_to_range(target, target_min = self.action_data.min_range, target_max = self.action_data.max_range, invert=self.action_data.invert_axis) 
                return self.block.execute(output_value)
                
            if self.action_data.mode == SimConnectActionMode.Trigger:
                pass
                    
            elif self.action_data.mode == SimConnectActionMode.SetValue:
                target = self.action_data.value
                return self.block.execute(target)
                pass
            
        elif value.current:
            # non joystick input (button)
            if not self.block.is_axis: 
                return self.block.execute(self.value)
            

        
        
        return True
    



class MapToSimConnect(gremlin.base_profile.AbstractContainerAction):

    """Action data for the map to keyboard action.

    Map to keyboard presses and releases a set of keys in sync with another
    physical input being pressed or released.
    """

    name = "Map to SimConnect"
    tag = "map-to-simconnect"

    default_button_activation = (True, True)
    # override allowed input types if different from default
    # input_types = [
    #     InputType.JoystickAxis,
    #     InputType.JoystickButton,
    #     InputType.JoystickHat,
    #     InputType.Keyboard
    # ]

    functor = MapToSimConnectFunctor
    widget = MapToSimConnectWidget

    @property
    def priority(self):
        return 9

    def __init__(self, parent):
        """Creates a new instance.

        :param parent the container this action is part of
        """
        super().__init__(parent)
        self.sm = SimConnectData()

        # the current command category if the command is an event
        self.category = SimConnectEventCategory.NotSet

        # the current command name
        self.command = None

        # the value to output if any
        self.value = None

        # the block for the command
        self.min_range = -16383
        self.max_range = 16383
        self.keys = None # keys to send
        self.gates = [] # list of GateData objects

        # output mode
        self.mode = SimConnectActionMode.NotSet

        # readonly mode
        self.is_readonly = False

        # invert axis input (axis inputs only)
        self.invert_axis = False

      

    def icon(self):
        """Returns the icon to use for this action.

        :return icon representing this action
        """
        return "mdi.airplane"
        

    def requires_virtual_button(self):
        """Returns whether or not an activation condition is needed.

        :return True if an activation condition is required for this particular
            action instance, False otherwise
        """
        return False

    def _parse_xml(self, node):
        """Reads the contents of an XML node to populate this instance.

        :param node the node whose content should be used to populate this
            instance
        """
        # if 
        # value  = safe_read(node,"category", str)
        # self.category = SimConnectEventCategory.to_enum(value, validate=False)
        command = safe_read(node,"command", str)
        if not command:
            command = SimConnectData().get_default_command()
        self.command = command
        self.value = safe_read(node,"value", float, 0)
        mode = safe_read(node,"mode", str, "none")
        self.mode = SimConnectActionMode.to_enum(mode)

        # axis inversion
        self.invert_axis = safe_read(node,"invert", bool, False)

        # load gate data
        self.gates = []
        gate_node = gremlin.util.get_xml_child(node,"gates")
        if gate_node:
            for child in gate_node:
                gate_data = gremlin.gated_handler.GateData(self)
                gate_data.from_xml(child)
                self.gates.append(gate_data)
    
    def _generate_xml(self):
        """Returns an XML node containing this instance's information.

        :return XML node containing the information of this  instance
        """
        node = ElementTree.Element(MapToSimConnect.tag)

        # simconnect command
        command = self.command if self.command else ""
        node.set("command",safe_format(command, str) )

        # fixed value
        value = self.value if self.value else 0.0
        node.set("value",safe_format(value, float))

        # action mode
        mode = SimConnectActionMode.to_string(self.mode)
        node.set("mode",safe_format(mode, str))

        # axis inversion
        node.set("invert",str(self.invert_axis))

        # save gate data
        if self.gates:
            node_gate = ElementTree.SubElement(node, "gates")
            for gate_data in self.gates:
                child = gate_data.to_xml()
                node_gate.append(child)


        return node

    def _is_valid(self):
        """Returns whether or not this action is valid.

        :return True if the action is configured correctly, False otherwise
        """
        return True


    def __getstate__(self):
        ''' serialization override '''
        state = self.__dict__.copy()
        # sm is not serialized, remove it
        del state["sm"]
        return state

    def __setstate__(self, state):
        ''' serialization override '''
        self.__dict__.update(state)
        # sm is not serialized, add it
        self.sm = SimConnectData()

version = 1
name = "map-to-simconnect"
create = MapToSimConnect
