# -*- coding: utf-8; -*-

# Copyright (C) 2015 - 2021 Lionel Ott
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import sys
sys.path.append(".")

import pytest
import uuid
from lxml import etree as ElementTree

import dinput
import gremlin.error as error
import gremlin.joystick_handling
import gremlin.types as types
import gremlin.profile_library as profile_library

import action_plugins.map_to_vjoy as map_to_vjoy


xml_button = """
    <action id="ac905a47-9ad3-4b65-b702-fbae1d133609" parent="ec663ba4-264a-4c76-98c0-6054058cae9f" type="remap">
        <property type="int">
            <name>vjoy-device-id</name>
            <value>1</value>
        </property>
        <property type="int">
            <name>vjoy-input-id</name>
            <value>12</value>
        </property>
        <property type="input_type">
            <name>vjoy-input-type</name>
            <value>button</value>
        </property>
        <property type="bool">
            <name>button-inverted</name>
            <value>false</value>
        </property>
    </action>
"""

xml_axis = """
    <action id="ac905a47-9ad3-4b65-b702-fbae1d133609" parent="ec663ba4-264a-4c76-98c0-6054058cae9f" type="remap">
        <property type="int">
            <name>vjoy-device-id</name>
            <value>2</value>
        </property>
        <property type="int">
            <name>vjoy-input-id</name>
            <value>6</value>
        </property>
        <property type="input_type">
            <name>vjoy-input-type</name>
            <value>axis</value>
        </property>
        <property type="axis_mode">
            <name>axis-mode</name>
            <value>relative</value>
        </property>
        <property type="float">
            <name>axis-scaling</name>
            <value>1.5</value>
        </property>
    </action>
"""


def test_ctor(joystick_init):
    r = map_to_vjoy.MapToVjoyModel(
        profile_library.ActionTree(),
        types.InputType.JoystickButton
    )

    assert r.vjoy_device_id == 1
    assert r.vjoy_input_id == 1
    assert r.vjoy_input_type == types.InputType.JoystickButton
    assert r.axis_mode == types.AxisMode.Absolute
    assert r.axis_scaling == 1.0


def test_from_xml():
    r = map_to_vjoy.MapToVjoyModel(
        profile_library.ActionTree(),
        types.InputType.JoystickButton
    )
    r.from_xml(ElementTree.fromstring(xml_button))
    assert r.vjoy_device_id == 1
    assert r.vjoy_input_id == 12
    assert r.vjoy_input_type == types.InputType.JoystickButton
    assert r.axis_mode == types.AxisMode.Absolute
    assert r.axis_scaling == 1.0

    r = map_to_vjoy.MapToVjoyModel(profile_library.ActionTree())
    r.from_xml(ElementTree.fromstring(xml_axis))
    assert r.vjoy_device_id == 2
    assert r.vjoy_input_id == 6
    assert r.vjoy_input_type == types.InputType.JoystickAxis
    assert r.axis_mode == types.AxisMode.Relative
    assert r.axis_scaling == 1.5


def test_to_xml():
    r = map_to_vjoy.MapToVjoyModel(
        profile_library.ActionTree(),
        types.InputType.JoystickButton
    )

    r._id = uuid.UUID("ac905a47-9ad3-4b65-b702-fbae1d133609")
    r.vjoy_device_id = 2
    r.vjoy_input_id = 14
    r.vjoy_input_type = types.InputType.JoystickButton

    node = r.to_xml()
    assert node.find(
            "./property/name[.='vjoy-device-id']/../value"
        ).text == "2"
    assert node.find(
            "./property/name[.='vjoy-input-id']/../value"
        ).text == "14"
    assert node.find(
            "./property/name[.='vjoy-input-type']/../value"
        ).text == "button"
    assert node.find("./property/name[.='axis-mode']") == None
    assert node.find("./property/name[.='axis-scaling']") == None

    r.vjoy_input_type = types.InputType.JoystickAxis
    r.axis_mode = types.AxisMode.Absolute
    r.axis_scaling = 0.75

    node = r.to_xml()
    assert node.find(
        "./property/name[.='vjoy-device-id']/../value"
    ).text == "2"
    assert node.find(
        "./property/name[.='vjoy-input-id']/../value"
    ).text == "14"
    assert node.find(
        "./property/name[.='vjoy-input-type']/../value"
    ).text == "axis"
    assert node.find(
        "./property/name[.='axis-mode']/../value"
    ).text == "absolute"
    assert node.find(
        "./property/name[.='axis-scaling']/../value"
    ).text == "0.75"
