from gremlin import util, error
import time
import json
import os
import pathlib

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class ControlsMappingReader(metaclass=Singleton):

    def __init__(self, controls_mapping):
        util.log("ControlsMappingReader::init " + time.strftime("%a, %d %b %Y %H:%M:%S"))
        util.log("ControlsMappingReader::mapping - " + controls_mapping)
        util.log("ControlsMappingReader::current directory - " + os.getcwd())
        self.controls_mapping = controls_mapping
        self.controls_list = []

    def getControlsMapping(self):
        util.log("ControlsMappingReader::getControlsMapping")
        if len(self.controls_list) == 0:
            util.log("ControlsMappingReader::loading - " + self.controls_mapping)
            util.log("ControlsMappingReader::current directory - " + os.getcwd())
            controls_mapping_file = os.path.join(os.getcwd(), self.controls_mapping)

            self.controls_list = []
            try:
                self.controls_list = json.loads(pathlib.Path(controls_mapping_file).read_text(encoding="UTF-8"))
            except:
                util.display_error("Unable to read in Controls Mapping. Make sure the Controls Mappings Settings is correct and file is available.")
                raise error.GremlinError(
                    "Unable to read in Controls Mapping"
                )
            util.log("ControlsMappingReader::mapping read successfully") 
        return self.controls_list
    

    def resetControlsMapping(self, controls_mapping):
        self.controls_list = []
        self.controls_mapping = controls_mapping