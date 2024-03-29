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

        try:
            self.controls_list = json.loads(pathlib.Path(controls_mapping).read_text(encoding="UTF-8"))
        except:
            util.display_error("Unable to read in Controls Mapping. Make sure the Controls Mappings Settings is correct and file is available.")
            self.pause()            
            raise error.GremlinError(
                "Unable to read in Controls Mapping"
            )
        
        util.log("ControlsMappingReader::mapping read successfully")


    def getControlsMapping(self):
        util.log("ControlsMappingReader::getControlsMapping")
        return self.controls_list
