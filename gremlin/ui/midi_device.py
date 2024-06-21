

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


import logging

from PySide6 import QtWidgets, QtCore


from gremlin.input_types import InputType
from gremlin.util import *
from xml.etree import ElementTree
from . import input_item, ui_common 
import gremlin.ui.device_tab 
import uuid
import mido
from gremlin.singleton_decorator import SingletonDecorator
import gremlin.ui.input_item 
import gremlin.ui.ui_common
import enum
from gremlin.util import parse_guid
import gremlin.event_handler
from gremlin.ui.device_tab import InputItemConfiguration

''' these MIDI objects are based on the MIDO and python-rtMIDI libraries '''

class MidiCommandType(enum.Enum):
    ''' list of supported MIDI command types '''
    Control = 0
    NoteOn = 1
    NoteOff = 2
    Aftertouch = 3
    ChannelAftertouch = 4
    PitchWheel = 5
    ProgramChange = 6
    SysEx = 7,

    @staticmethod
    def to_string(value):
        try:
            return _midi_to_string_lookup[value]
        except KeyError:
            raise ValueError("Invalid type in lookup")

    @staticmethod
    def to_enum(value):
        try:
            return _string_to_midi_lookup[value]
        except KeyError:
            raise ValueError("Invalid type in lookup")
        
    @staticmethod
    def to_list() -> list:
        return [it for it in MidiCommandType]

    @staticmethod
    def to_pairs() -> list:
        data = []
        for it in MidiCommandType:
            data.append((_midi_to_string_lookup[it], it))    
        return data
    @staticmethod
    def to_mido_type(value):
        ''' converts a gremlin type to a mido message type '''
        if value == MidiCommandType.Control:
            return "control_change"
        if value == MidiCommandType.NoteOn:
            return "note_on"
        if value == MidiCommandType.NoteOff:
            return "note_off"
        if value == MidiCommandType.Aftertouch:
            return "polytouch" # 0xA0 message
        if value == MidiCommandType.ChannelAftertouch:
            return "aftertouch" # 0xD0 message
        if value == MidiCommandType.ProgramChange:
            return "program_change"
        if value == MidiCommandType.PitchWheel:
            return "pitchwheel"
        if value == MidiCommandType.SysEx:
            return "sysex"
        return None
    
    @staticmethod
    def from_mido_type(value):
        ''' converts a mido message type to a gremlinex midi type - don't care messages return None '''
        if value == "control_change":
            return MidiCommandType.Control
        if value == "note_on":
            return MidiCommandType.NoteOn
        if value == "note_off":
            return MidiCommandType.NoteOff
        if value == "polytouch":
            return MidiCommandType.Aftertouch
        if value == "aftertouch":
            return MidiCommandType.ChannelAftertouch
        if value == "program_change":
            return MidiCommandType.ProgramChange
        if value == "pitchwheel":
            return MidiCommandType.PitchWheel
        if value == "sysex":
            return MidiCommandType.SysEx
        return None
    
    @staticmethod
    def byte_count(value):
        # returns byte count based on the command - returns -1 if unlimited, 2 or 3
        if value in (MidiCommandType.ProgramChange,
                     MidiCommandType.ChannelAftertouch
                     ):
            return 2
        if value == MidiCommandType.SysEx:
            return -1 # unlimited
        # all others
        return 3

        
        

 

_midi_to_string_lookup = {
    MidiCommandType.Control: "CC",
    MidiCommandType.NoteOn: "Note On",
    MidiCommandType.NoteOff: "Note Off",
    MidiCommandType.Aftertouch: "After Touch",
    MidiCommandType.ChannelAftertouch: "Channel Aftertouch",
    MidiCommandType.PitchWheel: "Pitchwheel",
    MidiCommandType.ProgramChange: "Program Change",
    MidiCommandType.SysEx:"SysEx",

}

_string_to_midi_lookup = {
    "CC": MidiCommandType.Control ,
    "Note On": MidiCommandType.NoteOn ,
    "Note Off": MidiCommandType.NoteOff,
    "After Touch": MidiCommandType.Aftertouch ,
    "Channel Aftertouch":MidiCommandType.ChannelAftertouch,
    "Pitchwheel": MidiCommandType.PitchWheel,
    "Program Change":MidiCommandType.ProgramChange,
    "SysEx": MidiCommandType.SysEx,
    
}


class MidiInputItem():
    ''' holds the data for a MIDI device '''
    def __init__(self):
        self.id = None # GUID
        self._port_name = None
        self._message = None # the midi message
        self._display_name =  "MIDI (not configured)"
        self._display_tooltip = "Input configuration not set"
        self._command = None # decoded command


    @property
    def message(self):
        return self._message
    
    @message.setter
    def message(self, value):
        self._message = value
        self._update_display_name()

    @property
    def port_name(self):
        return self._port_name
    
    @property
    def command(self):
        return self._command
    
    @port_name.setter
    def port_name(self, value):
        self._port_name = value
        self._update_display_name()


    def parse_xml(self, node):
        ''' reads an input item from xml '''
        if node.tag == "input":
            self.id = read_guid(node, "guid")
            self.port_name = safe_read(node, "port", str)
            data = safe_read(node,"data", str)
            bytes = byte_string_to_list(data)
            self.message = mido.Message.from_bytes(bytes) if bytes else None


    def to_xml(self):
        ''' writes the input item to XML'''
        node = ElementTree.Element("input")
        node.set("guid", str(self.id))
        node.set("port", str(self.port_name))
        data = [] if self.message is None else self.message.bytes()
        node.set("data", byte_list_to_string(data))
        return node
    
    @property
    def display_name(self):
        ''' display name for this input '''
        return self._display_name

    @property
    def display_tooltip(self):
        ''' detailed tooltip '''
        return self._display_tooltip

    def _update_display_name(self):
        port_name = self._port_name if self._port_name else "[No port]"
        if self.message:
            message = self.message
            mido_type = message.type
            command = MidiCommandType.from_mido_type(mido_type)
            command_display = MidiCommandType.to_string(command)
            self._display_name = f"MIDI {port_name}/{command_display}/{message.channel}/{message.hex()}"
            if command == MidiCommandType.Control:
                stub = f"<b>Control:</b> {message.control}<br><b>Value:</b> {message.value} (0x{message.value:02X})"
            elif command in (MidiCommandType.NoteOff, MidiCommandType.NoteOn):
                stub = f"<b>Note:</b> {message.note}<br><b>Velocity:</b> {message.velocity} (0x{message.velocity:02X})"
            elif command == MidiCommandType.Aftertouch:
                stub = f"<b>Note:</b> {message.note}<br>Pressure:</b> {message.value} (0x{message.value:02X})"
            elif command == MidiCommandType.ChannelAftertouch:  
                stub = f"<b>Pressure:</b> {message.value} (0x{message.value:02X})"
            elif command == MidiCommandType.ProgramChange:
                stub = f"<b>Program:</b> {message.program} (0x{message.program:02X})"
            elif command == MidiCommandType.PitchWheel:
                stub = f"<b>Program:</b> {message.pitch} (0x{message.pitch:04X})"
            else:
                stub = f"</b>Unable to decode:</b> {command}"

            self._command = command

            self._display_tooltip = f"<b>MIDI Configuration:</b><br/><b>Port:</b> {port_name}<br/><b>Command:</b> {command_display}<br/><b>Channel:</b> {self.message.channel}<br/>{stub}<br/><b>Bytes (hex):</b> {self.message.hex()}"
        else:
            self._display_name = f"MIDI {port_name}/(not configured)"


    def __hash__(self):
        return str(self.id).__hash__()
    
    def __lt__(self, other):
        ''' used for sorting purposes '''        
        # keep as is (don't sort)
        return False
    
    # def __eq__(self, other):
    #     ''' compares two midi inputs to see if they are the same '''

        
    #     if self.message is not None and other.message is not None:
    #         return self.message == other.message
    #     if self.message is None and other.message is None:
    #         return True
    #     return False



class MidiListener(QtCore.QThread):
    ''' midi input object '''

    def __init__(self, port_name, port_number, callback, parent=None):
        ''' creates a MIDI input port listener - messages received will be sent via the message_received event
        :param device - the midi device (rtmidi.device)
        :param port_name - the midi port name 
        :param port_number - the midi port number returned by the port scan, zero based index
        '''


        super().__init__(parent)
        self.port_number = port_number
        self.port_name = port_name
        self.callback = callback
        self.finished.connect(self._finished)


    def run(self):
        with mido.open_input(self.port_name) as inport:
            logging.getLogger("system").info(f"Midinput: open port {self.port_number}")
            while not self.isInterruptionRequested():
                for message in inport.iter_pending():
                    logging.getLogger("system").info(f"Midinput: heard message: {message}")
                    self.callback(self.port_name, self.port_number, message)
                time.sleep(0.1)
            logging.getLogger("system").info(f"Midinput: close port {self.port_number}")



    def _finished(self):
        ''' called when the listener is closed '''
        logging.getLogger("system").info(f"Midinput: finished")
        self.deleteLater()



@SingletonDecorator
class MidiInterface(QtCore.QObject):
    ''' midi interface to gremlinex

        this wraps rtMidi to process inbound MIDI messages, opens and closes ports and triggers a midi_message event with the MIDI port info and data for each message
       
    '''

    midi_message = QtCore.Signal(str, int, object)  # port_name, port_index, midi_message
    
    def __init__(self):
        ''' setup the midi interface '''
        super().__init__()


        self._started = False # true if the interface is actively listening
        self._listeners = {} # map of port numer to its listener


        

        # get a list of available devices to listen into
        mido.set_backend('mido.backends.rtmidi')
        self._port_names = []
        self._port_map = {}
        for index, name in enumerate(mido.get_input_names()):
            self._port_names.append(name)
            self._port_map[name] = index
        self._port_count = len(self._port_names)

        self._port_names.sort()

        for port in self._port_names:
            logging.getLogger("system").info(f"MIDI device detected: {port}")

    def start(self, port_name_or_list = None):
        ''' starts listeners 
        
        :param port_name_or_list  
            if int - single port name to open
            if a list - list of ports names to open
            if none - opens all known ports 
        
        '''

        # request start
        if self._started:
            self.stop()


        self._monitored_ports = set() # holds the list of active port numbers 
        if port_name_or_list is None:
            # open all ports
            self._monitored_ports = set(range(self._port_count))
        else:
            if isinstance(port_name_or_list, str):
                port_list = [port_name_or_list]
            elif isinstance(port_name_or_list, list):
                port_list = port_name_or_list
            else:
                raise ValueError(f"MIDI: don't know how to handle start parameter {port_name_or_list}")
            
            for port_name in port_list:
                port_number = self._port_map[port_name]
                self._monitored_ports.add(port_number)


        # start the listeners
        for port_number in self._monitored_ports:
            port_name = self._port_names[port_number]
            logging.getLogger("system").info(f"MIDI Interface: START listen requested on port: {port_name} [{port_number}]")
            listener = MidiListener(port_name, port_number, self._message_cb)
            listener.start()
            self._listeners[port_number] = listener

        self._started = True

    def stop(self):
        # request stop
        logging.getLogger("system").info(f"MIDI Interface: STOP listen requested")


        for port_number in self._monitored_ports:
            listener : MidiListener
            listener = self._listeners[port_number]
            if listener.isRunning():
                # request exit and wait for it
                listener.requestInterruption() # request terminate
                listener.wait()
            logging.getLogger("system").info(f"MIDI Interface: port [{port_number}] stopped")
            del self._listeners[port_number]

        # clear
        self._monitored_ports = set()
        self._started = False

    def _message_cb(self, port_name, port_index, message):
        ''' called when a MIDI message is received '''
        self.midi_message.emit(port_name, port_index, message)

    @property
    def ports(self):
        ''' returns a list of MIDI port names '''
        return self._port_names
    



    
class MidiInputListenerWidget(QtWidgets.QFrame):

    """ opens a centered modal midi message listener dialog
    
        grabs the first MIDI message it hears and closes 

        also closes on esc key press 
       
    """

    def __init__(
            self,
            callback,
            port_name,
            parent=None
    ):
        """Creates a new instance.

        :param callback the function to pass the key pressed by the
            user to
        :param event_types the events to capture and return
        :param return_kb_event whether or not to return the kb event (True) or
            the key itself (False)
        :param multi_keys whether or not to return multiple key presses (True)
            or return after the first initial press (False)
        :param filter_func function applied to inputs which filters out more
            complex unwanted inputs
        :param parent the parent widget of this widget
        """
        super().__init__(parent)
        from gremlin.shared_state import set_suspend_input_highlighting


        # setup and listen for the midi message
        self._interface = MidiInterface()
        self._interface.midi_message.connect(self._midi_message)
        self._callback = callback

        if port_name and not port_name in self._interface.ports:
            logging.getLogger("system").error(f"MIDI listener: invalid port name: {port_name}")
            self.close()
            return
        
        self.port = port_name
        self.message = None
        
        # Create and configure the ui overlay
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.addWidget(
            QtWidgets.QLabel(f"""<center>Please press a MIDI input going to port {port_name if port_name else '(all)'}.<br/><br/>Press ESC to abort.</center>""")
        )

        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setFrameStyle(QtWidgets.QFrame.Plain | QtWidgets.QFrame.Box)
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColorConstants.DarkGray)
        self.setPalette(palette)

        # Disable ui input selection on joystick input
        set_suspend_input_highlighting(True)

        # listen for the escape key
        event_listener = gremlin.event_handler.EventListener()
        event_listener.keyboard_event.connect(self._kb_event_cb)

        # start listening on all ports 
        self._interface.start(port_name)


    def _kb_event_cb(self, event):
        from gremlin.keyboard import key_from_code, key_from_name
        key = key_from_code(
                event.identifier[0],
                event.identifier[1]
        )
        if event.is_pressed and key == key_from_name("esc"):

            # stop listening
            self._interface.stop()

            # close the winow
            self.close()

    def _midi_message(self, port_name : str, port_index : int,  message :mido.Message ):
        ''' called when a midi messages is provided by the listener '''
        if self.message is None:
            # only grab the first message received
            self.message = message
            self._callback(port_name, port_index, message)

        self.close()


class MidiInputConfigDialog(QtWidgets.QDialog):
    ''' dialog showing the MIDI input configuration options '''

    def __init__(self, index, data, parent):
        '''
        :param index - the input item index zero based
        :param identifier - the input item identifier 
        '''
        super().__init__(parent)
        # self._sequence = InputKeyboardModel(sequence=sequence)
        main_layout = QtWidgets.QVBoxLayout()
        self.setWindowTitle("Midi Input Mapper")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self._parent = parent # list view
        assert hasattr(parent, "input_item_list_model"),"MIDI CONFIG: Parent widget does not have required listview model"
        assert hasattr(parent, "input_item_list_view"),"MIDI CONFIG: Parent widget does not have required listview"
                       

        self.config_widget =  QtWidgets.QWidget()
        self.config_layout = QtWidgets.QGridLayout()
        self.config_widget.setLayout(self.config_layout)
        
        self.index = index
        self.identifier = data
        self._valid = True # assume valid

        # midi message
        self._midi_message = None
        self._port_name = None

        interface : MidiInterface = MidiInterface()

        # MIDI port selector
        self._midi_port_selector_widget = QtWidgets.QComboBox()
        ports = interface.ports
        self._midi_port_selector_widget.addItems(ports)
        self._midi_port_selector_widget.currentIndexChanged.connect(self._update_port)

        self._midi_command_selector_widget = QtWidgets.QComboBox()
        for name, it in MidiCommandType.to_pairs():
            self._midi_command_selector_widget.addItem(name, it)
        self._midi_command_selector_widget.currentIndexChanged.connect(self._update_command)

        a_widget = QtWidgets.QSpinBox()
        a_widget.setRange(0,127)
        self._midi_data_a_widget = a_widget
        self._midi_data_a_widget.valueChanged.connect(self._update_message)

        b_widget = QtWidgets.QSpinBox()
        b_widget.setRange(0,127)
        self._midi_data_b_widget = b_widget
        self._midi_data_b_widget.valueChanged.connect(self._update_message)

        channel_widget = QtWidgets.QSpinBox()
        channel_widget.setRange(1, 11)
        self._midi_channel_selector_widget = channel_widget
        self._midi_channel_selector_widget.valueChanged.connect(self._update_channel)

        # holds a list of input bytes for sysex
        self._midi_data_widget = QtWidgets.QLineEdit()
        self._midi_data_widget.setVisible(False)
        self._midi_data_label = QtWidgets.QLabel("Sysex Data")
        self._midi_data_label.setVisible(False)

        # MIDI message type to listen to CC, note_on, not_off and sysex message
        col = 0
        self.config_layout.addWidget(QtWidgets.QLabel("Port"), 0, col)
        self.config_layout.addWidget(self._midi_port_selector_widget, 1, col)

        col +=1
        self.config_layout.addWidget(QtWidgets.QLabel("Channel (1..11)"), 0, col)
        self.config_layout.addWidget(self._midi_channel_selector_widget, 1, col)        

        col +=1
        self.config_layout.addWidget(QtWidgets.QLabel("Command"), 0, col)
        self.config_layout.addWidget(self._midi_command_selector_widget, 1, col)

        col +=1
        sysex_col = col
        self._midi_data_a_label = QtWidgets.QLabel("Data 1 (0..127)")
        self.config_layout.addWidget(self._midi_data_a_label, 0, col)
        self.config_layout.addWidget(self._midi_data_a_widget, 1, col)

        col +=1
        self._midi_data_b_label = QtWidgets.QLabel("Data 2 (0..127)")
        self.config_layout.addWidget(self._midi_data_b_label, 0, col)
        self.config_layout.addWidget(self._midi_data_b_widget, 1, col)

        
        self.config_layout.addWidget(self._midi_data_label, 0, sysex_col)
        self.config_layout.addWidget(self._midi_data_widget, 1, sysex_col, 1, -1)


        self.ok_widget = QtWidgets.QPushButton("Ok")
        self.ok_widget.clicked.connect(self._ok_button_cb)

        self.cancel_widget = QtWidgets.QPushButton("Cancel")
        self.cancel_widget.clicked.connect(self._cancel_button_cb)

        self.button_widget = QtWidgets.QWidget()
        self.button_layout = QtWidgets.QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)

        # listen all ports button 
        self.listen_widget = QtWidgets.QPushButton("Listen (All)")
        self.listen_widget.clicked.connect(self._listen_cb)

        # listen current port button
        self.listen_filter_widget = QtWidgets.QPushButton("Listen")
        self.listen_filter_widget.clicked.connect(self._listen_port_cb)



        self.button_layout.addWidget(self.listen_widget)
        self.button_layout.addWidget(self.listen_filter_widget)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.ok_widget)
        self.button_layout.addWidget(self.cancel_widget)

        # midi message repeater 
        self._midi_message_widget = QtWidgets.QLabel()

        # validation message
        self._validation_message_widget = gremlin.ui.ui_common.QIconLabel()

        
        main_layout.addWidget(self.config_widget)
        main_layout.addWidget(self._midi_message_widget)
        main_layout.addWidget(self._validation_message_widget)
        main_layout.addWidget(gremlin.ui.ui_common.QHLine())
        main_layout.addWidget(self.button_widget)

        self.setLayout(main_layout)

        # load the identifier
        if data:
            input_id : MidiInputItem = data
            message = input_id.message
            port_name = input_id.port_name
            if message:
                self._port_name = port_name
                port_index = self._midi_port_selector_widget.findText(port_name)
                if port_index != -1:
                    # port name isn't found anymore 
                    self._midi_message = message
                    self._load_message(port_name, port_index, message)
                else:
                    logging.getLogger("system").error(f"MIDI config: unable to find port {port_name} - skipping load")
        
        self.command = self._midi_command_selector_widget.currentData()
        self.port_name = self._midi_port_selector_widget.currentText()
        self.channel = self._midi_channel_selector_widget.value()
        self._update_message()

    def _update_display(self):
        command = self.command
        show_sysex = command == MidiCommandType.SysEx
        display_b_data = not show_sysex
        display_a_data = not show_sysex
        max_a_range = 127

        if command == MidiCommandType.Control:
            self._midi_data_a_label.setText("Control (0..127)")
            self._midi_data_b_label.setText("Value (0..127)")

        elif command in (MidiCommandType.NoteOff, MidiCommandType.NoteOn):
            self._midi_data_a_label.setText("Note (0..127)")
            self._midi_data_b_label.setText("Velocity (0..127)")
            
        elif command == MidiCommandType.Aftertouch:
            self._midi_data_a_label.setText("Note (0..127)")
            self._midi_data_b_label.setText("Pressure (0..127)")
            
        elif command == MidiCommandType.ChannelAftertouch:
            self._midi_data_a_label.setText("Value (0..127)")
            display_b_data = False
        elif command == MidiCommandType.ProgramChange:
            self._midi_data_a_label.setText("Program (0..127)")
            display_b_data = False
        elif command == MidiCommandType.PitchWheel:
            self._midi_data_a_label.setText("Value (0..16383)")
            max_a_range = 16383

        self._midi_data_widget.setVisible(show_sysex)
        self._midi_data_label.setVisible(show_sysex)
        self._midi_data_a_label.setVisible(display_a_data)
        self._midi_data_a_widget.setVisible(display_a_data)
        self._midi_data_b_label.setVisible(display_b_data)
        self._midi_data_b_widget.setVisible(display_b_data)

        # update range based on command type
        self._midi_data_a_widget.setRange(0, max_a_range)

        # update port specific listen
        self.listen_filter_widget.setText(f"Listen ({self.port_name})")

    def _update_command(self):
        command = self._midi_command_selector_widget.currentData()
        self.command = command
        self._update_message()

    def _update_port(self):
        self._port_name = self._midi_port_selector_widget.currentText()
        self._update_message()

    def _update_channel(self):
        self.channel = self._midi_channel_selector_widget.value()
        self._update_message()
    
    def _update_message(self):
        ''' updates the MIDI message that will be listened to '''
        
        channel = self._midi_channel_selector_widget.value()
        byte_channel = channel - 1 # channel is zero based in midi
        
        v1 = self._midi_data_a_widget.value()
        v2 = self._midi_data_a_widget.value()
        show_sysex = self.command == MidiCommandType.SysEx

        command = self.command
        mido_type = MidiCommandType.to_mido_type(command) # map to a mido message type

        message = None
        if show_sysex:
            # sysex message 
            data_str = self._midi_data_widget.value()
            data = byte_string_to_list(data_str)

            message = mido.Message("sysex")
            message.data = data
        else:
            # other message
            message = mido.Message(mido_type)
            message.channel = byte_channel
            if command == MidiCommandType.Control:
                message.control = v1
                message.value = v2
            elif command in (MidiCommandType.NoteOff, MidiCommandType.NoteOn):
                message.note = v1
                message.velocity = v2                    
            elif command == MidiCommandType.Aftertouch:
                message.note = v1
                message.value = v2
            elif command == MidiCommandType.ChannelAftertouch:
                message.value = v1
            elif command == MidiCommandType.ProgramChange:
                message.program = v1
            elif command == MidiCommandType.PitchWheel:
                message.pitch = v1
        
        if message is None:
            raise ValueError(f"Don't now how to handle command type: {command}")


                
            
        self._midi_message = message
        self._validate()
        self._update_display()
        self._update_status(update = False)

        

    def _update_status(self, update = False):
        # updates the status and message 
        # build the midi message including display and byte sequence
        message : mido.Message
        message = self.midi_message
        if message:
            channel = message.channel + 1
            msg_hex = self.midi_message.hex()
            cmd = MidiCommandType.from_mido_type(message.type)
            cmd_s = MidiCommandType.to_string(cmd)
            msg = f"Port: {self.port_name} Channel: {channel} Cmd: {cmd_s} ({msg_hex})"
        else:
            msg = "No valid message"
        
        self._midi_message_widget.setText(msg)


    @property
    def port_name(self):
        return self._port_name
        
    
    @port_name.setter
    def port_name(self, value):
        if self._port_name != value:
            self._midi_port_selector_widget.setCurrentText(value)
            self._port_name = value
    
    @property
    def command(self):
        ''' returns the currently selected midi command '''
        return self._midi_command_selector_widget.currentData()
    
    @command.setter
    def command(self, value):
        ''' sets the command '''
        
        if isinstance(value, str):
            cmd = MidiCommandType.to_enum(value)
        else:
            cmd = value

        index =  self._midi_command_selector_widget.findData(cmd)
        self._midi_command_selector_widget.setCurrentIndex(index)
    
    @property
    def value_one(self):
        ''' returns the first value '''
        return self._midi_data_a_widget.value()
    
    @value_one.setter
    def value_one(self, value):
        self._midi_data_a_widget.setValue(value)
    
    @property
    def value_two(self):
        ''' returns the first value '''
        return self._midi_data_b_widget.value()    
    
    @value_two.setter
    def value_two(self, value):
        self._midi_data_b_widget.setValue(value)    

    @property
    def channel(self):
        ''' MIDI channel 1 to 16 '''
        return self._midi_channel_selector_widget.value()
    
    @channel.setter
    def channel(self, value):
        self._midi_channel_selector_widget.setValue(value)    


    @property
    def midi_message(self) -> mido.Message:
        ''' MIDI message as edited '''
        return self._midi_message

    def _ok_button_cb(self):
        ''' ok button pressed '''
        self.accept()
        
    def _cancel_button_cb(self):
        ''' cancel button pressed '''
        self.reject()        

    def _listen_port_cb(self):
        self._listen_cb(True)
    
    def _listen_cb(self, current_port_only = False):
        ''' listens to an inbound MIDI message '''
        port_name = self.port_name if current_port_only else None
        self.listener_dialog = MidiInputListenerWidget(self._load_message, port_name)

        # Display the dialog centered in the middle of the UI
        root = self
        while root.parent():
            root = root.parent()
        geom = root.geometry()

        self.listener_dialog.setGeometry(
            int(geom.x() + geom.width() / 2 - 150),
            int(geom.y() + geom.height() / 2 - 75),
            300,
            150
        )
        self.listener_dialog.show()        

    def _load_message(self, port_name : str, port_index : int, message : mido.Message):
        ''' load the config from a MIDI message '''
        # decode the message 
        
        mido_type = message.type
        command = MidiCommandType.from_mido_type(mido_type)
        if not command:
            return # not a valid type
        channel = message.channel + 1

        # set the port
        with QtCore.QSignalBlocker(self._midi_port_selector_widget):
            self._midi_port_selector_widget.setCurrentText(port_name)

        # set the command
        with QtCore.QSignalBlocker(self._midi_command_selector_widget):
            index = self._midi_command_selector_widget.findData(command)
            self._midi_command_selector_widget.setCurrentIndex(index)        

        # set the channel
        with QtCore.QSignalBlocker(self._midi_channel_selector_widget):
            self._midi_channel_selector_widget.setValue(channel)

        

        if command == MidiCommandType.SysEx:
            # grab the sysex data
            data = message.data
            hex_data = ""
            for byte in data:
                hex_data += f"{byte:02X} "
            hex_data.pop()
            self._midi_data_widget.setText(hex_data)

            logging.getLogger("system").info(f"MIDI: set port: {port_name} cmd: {command} data: {data}")
        else:
            v2 = 0
            if command == MidiCommandType.PitchWheel:
                # uses a 14 bit value - ensure the control will take it
                self._midi_data_a_widget.setRange(0, 16383)
                v1 = message.pitch
            elif command == MidiCommandType.Control:
                v1 = message.control
                v2 = message.value
            elif command in (MidiCommandType.NoteOff, MidiCommandType.NoteOn):
                v1 = message.note
                v2 = message.velocity
            elif command in (MidiCommandType.Aftertouch):
                v1 = message.note 
                v2 = message.value
            elif command == MidiCommandType.ChannelAftertouch:
                v1 = message.value
            elif command == MidiCommandType.ProgramChange:
                v1 = message.program
            else:
                raise ValueError(f"MIDI _load_message(): don't know how ot handle command: {command}")


            logging.getLogger("system").info(f"MIDI: set port: {port_name} cmd: {command} V1 {v1}/{v1:02X} V2 {v2}/{v2:02x}")
            
              
            with QtCore.QSignalBlocker(self._midi_data_a_widget):
                self._midi_data_a_widget.setValue(v1)


            with QtCore.QSignalBlocker(self._midi_data_b_widget):
                    self._midi_data_b_widget.setValue(v2)
            
            
            
        

        self._midi_message = message
        self._validate()
        self._update_display()            
        self._update_status()


    def _validate(self):
        ''' validates the input to ensure it does not conflict with an existing input '''
        # assume ok
        self._validation_message_widget.setText("")
        if self._midi_message is not None:
            # get the list of all the other inputs
            parent_widget = self._parent
            model : input_item.InputItemListModel = parent_widget.input_item_list_model
            self_bytes = self._midi_message.bytes()
            for index in range(model.rows()):
                widget = parent_widget.itemAt(index)
                if widget == self: continue # skip us
                # grab the input's configured midi message
                other_message = widget.identifier.input_id.message
                if other_message is None:
                    # input not set = ok
                    continue 
                other_bytes = other_message.bytes()
                if self_bytes == other_bytes:
                    self._validation_message_widget.setText(f"Input conflict detected with input [{index+1}] - ensure inputs are unique")
                    self._validation_message_widget.setIcon("fa.warning",True)
                    return False
            
        # no conflicts
        self._validation_message_widget.setText()
        self._validation_message_widget.setIcon()

        return True


        
        
        
            


class MidiDeviceTabWidget(QtWidgets.QWidget):

    """Widget used to configure open sound control (OSC) inputs """

    device_guid = parse_guid('1b56ecf7-0624-4049-b7b3-8d9b7d8ed7e0')

    def __init__(
            self,
            device_profile,
            current_mode,
            parent=None
    ):
        """Creates a new object instance.

        :param device_profile profile data of the entire device
        :param current_mode currently active mode
        :param parent the parent of this widget
        """
        super().__init__(parent)

        # list of input widgets by index position
        self._widget_map = {}

        # Store parameters
        self.device_profile = device_profile
        self.current_mode = current_mode

        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.left_panel_layout = QtWidgets.QVBoxLayout()
        self.device_profile.ensure_mode_exists(self.current_mode)
        self.widget_storage = {}

        # List of inputs
        self.input_item_list_model = input_item.InputItemListModel(
            device_profile,
            current_mode,
            [InputType.Midi] # only allow MIDI inputs for this widget
        )
        
        # create a list view with custom input widgets
        self.input_item_list_view = input_item.InputItemListView(custom_widget_handler=self._custom_widget_handler)
        self.input_item_list_view.setMinimumWidth(350)

        # Input type specific setups
        self.input_item_list_view.set_model(self.input_item_list_model)
        self.input_item_list_view.redraw()

        # Handle user interaction
        self.input_item_list_view.item_selected.connect(self._select_item_cb)
        self.input_item_list_view.item_edit.connect(self._edit_item_cb)
        self.input_item_list_view.item_closed.connect(self._close_item_cb)

        self.left_panel_layout.addWidget(self.input_item_list_view)
        self.main_layout.addLayout(self.left_panel_layout,1)

        # add a blank input configuration if nothing is selected - the configuration widget is always the second widget of the main layout
        right_panel = self.main_layout.takeAt(1)
        if right_panel is not None and right_panel.widget():
            right_panel.widget().hide()
            right_panel.widget().deleteLater()
        if right_panel:
            self.main_layout.removeItem(right_panel)

        widget = InputItemConfiguration()     
        self.main_layout.addWidget(widget,3)

        button_container_widget = QtWidgets.QWidget()
        button_container_layout = QtWidgets.QHBoxLayout()
        button_container_widget.setLayout(button_container_layout)

        # clear inputs button
        clear_button = ui_common.ConfirmPushButton("Clear MIDI Inputs", show_callback = self._show_clear_cb)
        clear_button.confirmed.connect(self._clear_inputs_cb)
        button_container_layout.addWidget(clear_button)
        button_container_layout.addStretch(1)

        # add input button
        add_input_button = QtWidgets.QPushButton("Add MIDI Input")
        add_input_button.clicked.connect(self._add_input_cb)

        button_container_layout.addWidget(add_input_button)

        self.left_panel_layout.addWidget(button_container_widget)

        # Select default entry
        if self.input_item_list_model.rows() > 0:
            selected_index = self.input_item_list_view.current_index
            if selected_index is not None:
                self._select_item_cb(selected_index)

    def display_name(self, input_id):
        ''' returns the name for the given input ID '''
        return input_id.display_name
        

    def _show_clear_cb(self):
        return self.input_item_list_model.rows() > 0

    def _clear_inputs_cb(self):
        ''' clears all input keys '''
        self.input_item_list_model.clear()
        self.input_item_list_view.redraw()

    def itemAt(self, index):
        ''' returns the input widget at the given index '''
        if index in self._widget_map.keys():
            return self._widget_map[index]
        return None



    def _select_item_cb(self, index):
        """Handles the selection of an input item.

        :param index the index of the selected item
        """

        item_data = self.input_item_list_model.data(index)

        right_panel = self.main_layout.takeAt(1)
        if right_panel is not None and right_panel.widget():
            right_panel.widget().hide()
            right_panel.widget().deleteLater()
        if right_panel:
            self.main_layout.removeItem(right_panel)

        widget = InputItemConfiguration(item_data)
        self.main_layout.addWidget(widget,3)            

        if item_data:
            
            # Create new configuration widget
            
            change_cb = self._create_change_cb(index)
            widget.action_model.data_changed.connect(change_cb)
            widget.description_changed.connect(change_cb)
    


  
    def _add_input_cb(self):
        """Adds a new input to the inputs list  """
        input_type = InputType.Midi
        input_id = MidiInputItem()
        input_id.id = uuid.uuid4() # unique ID for this new item
        self.device_profile.modes[self.current_mode].get_data(input_type, input_id)
        self.input_item_list_model.refresh()
        self.input_item_list_view.redraw()
        self.input_item_list_view.select_item(self._index_for_key(input_id),True)

        # auto edit input
        index = self.input_item_list_view.current_index
        self._edit_item_cb(None, index, input_id)


    def _index_for_key(self, input_id):
        ''' returns the index of the selected input id'''
        mode = self.device_profile.modes[self.current_mode]
        sorted_keys = list(mode.config[InputType.Midi].keys())
        return sorted_keys.index(input_id)
        

   

    def _create_change_cb(self, index):
        """Creates a callback handling content changes.

        :param index the index of the content being changed
        :return callback function redrawing changed content
        """
        return lambda: self.input_item_list_view.redraw_index(index)

    def set_mode(self, mode):
        ''' changes the mode of the tab '''        
        self.current_mode = mode
        self.device_profile.ensure_mode_exists(self.current_mode)
        self.input_item_list_model.mode = mode

        # Remove the existing widget, if there is one
        item = self.main_layout.takeAt(1)
        if item is not None and item.widget():
            item.widget().hide()
            item.widget().deleteLater()
        if item:
            self.main_layout.removeItem(item)

    def mode_changed_cb(self, mode):
        """Handles mode change.

        :param mode the new mode
        """
        self.set_mode(mode)


    def refresh(self):
        """Refreshes the current selection, ensuring proper synchronization."""
        pass
        # self.input_item_selected_cb(self.input_item_list_view.current_index)


    def _custom_widget_handler(self, list_view, index : int, identifier, data):
        ''' creates a widget for the input 
        
        the widget must have a selected property
        :param list_view The list view control the widget to create belongs to
        :param index The index in the list starting at 0 being the top item
        :param identifier the InpuIdentifier for the input list
        :param data the data associated with this input item
        
        '''

        widget = gremlin.ui.input_item.InputItemWidget(identifier = identifier, populate_ui = self._populate_input_widget_ui, populate_name= self._populate_name)
        input_id = identifier.input_id
        widget.create_action_icons(data)
        widget.update_description(data.description)
        widget.enable_close()
        widget.enable_edit()
        # remember what widget is at what index
        self._widget_map[index] = widget

        return widget

    

    def _create_close_callback(self, index):
        ''' creates a callback to handle the closing of items '''
        return lambda x: self._close_item(index)
    
    
    def _create_edit_callback(self, index):
        ''' creates a callback to handle the edit of items '''
        return lambda x: self._edit_item(index)
                    
    
    def _edit_item_cb(self, widget, index, data):
        ''' called when the edit button is clicked  '''
        self._edit_dialog = MidiInputConfigDialog(index, data, self)
        self._edit_dialog.accepted.connect(self._dialog_ok_cb)
        self._edit_dialog.showNormal()

    def _dialog_ok_cb(self):
        ''' called when the ok button is pressed on the edit dialog '''
        message = self._edit_dialog.midi_message
        index = self._edit_dialog.index
        port_name = self._edit_dialog.port_name


        data = self.input_item_list_model.data(index)
        data.input_id.port_name = port_name
        data.input_id.message = message
        
        self.input_item_list_view.redraw()
        

    def _close_item_cb(self, widget, index, data):
        ''' called when the close button is clicked '''
        self.model.removeRow(index)
        pass                    
    
    def _populate_input_widget_ui(self, input_widget, container_widget):
        ''' called when a button is created for custom content '''
        data : MidiInputItem = input_widget.identifier.input_id 
        label = gremlin.ui.ui_common.QIconLabel(text=data.display_name)
        
        if data.message is None:
            label.setIcon("fa.warning", use_qta=True)
        layout = QtWidgets.QHBoxLayout()
        container_widget.setLayout(layout)
        layout.addWidget(label)
        container_widget.parent().setToolTip(data.display_tooltip)

        


    def _populate_name(self, widget, identifier):        
        return "MIDI input"
    


