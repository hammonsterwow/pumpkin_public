from __future__ import annotations

import importlib.util
import sys
import types
from importlib.machinery import ModuleSpec
from pathlib import Path


if importlib.util.find_spec("rclpy") is None:
    rclpy_module = types.ModuleType("rclpy")
    rclpy_node_module = types.ModuleType("rclpy.node")
    rclpy_executors_module = types.ModuleType("rclpy.executors")
    rclpy_module.__spec__ = ModuleSpec("rclpy", loader=None)
    rclpy_node_module.__spec__ = ModuleSpec("rclpy.node", loader=None)
    rclpy_executors_module.__spec__ = ModuleSpec("rclpy.executors", loader=None)

    class Node:
        pass

    class ExternalShutdownException(Exception):
        pass

    rclpy_node_module.Node = Node
    rclpy_executors_module.ExternalShutdownException = ExternalShutdownException
    rclpy_module.node = rclpy_node_module
    rclpy_module.init = lambda *args, **kwargs: None
    rclpy_module.spin = lambda *args, **kwargs: None
    rclpy_module.shutdown = lambda *args, **kwargs: None
    rclpy_module.ok = lambda: True
    sys.modules["rclpy"] = rclpy_module
    sys.modules["rclpy.node"] = rclpy_node_module
    sys.modules["rclpy.executors"] = rclpy_executors_module

if importlib.util.find_spec("std_msgs") is None:
    std_msgs_module = types.ModuleType("std_msgs")
    std_msgs_msg_module = types.ModuleType("std_msgs.msg")
    std_msgs_module.__spec__ = ModuleSpec("std_msgs", loader=None)
    std_msgs_msg_module.__spec__ = ModuleSpec("std_msgs.msg", loader=None)

    class String:
        def __init__(self):
            self.data = ""

    class Bool:
        def __init__(self):
            self.data = False

    std_msgs_msg_module.String = String
    std_msgs_msg_module.Bool = Bool
    std_msgs_module.msg = std_msgs_msg_module
    sys.modules["std_msgs"] = std_msgs_module
    sys.modules["std_msgs.msg"] = std_msgs_msg_module

if importlib.util.find_spec("nlu") is None:
    nlu_module = types.ModuleType("nlu")
    nlu_config_module = types.ModuleType("nlu.config")
    nlu_module.__spec__ = ModuleSpec("nlu", loader=None)
    nlu_config_module.__spec__ = ModuleSpec("nlu.config", loader=None)

    class StructureBNLUPredictor:
        pass

    nlu_module.StructureBNLUPredictor = StructureBNLUPredictor
    nlu_config_module.DEFAULT_CONFIDENCE_THRESHOLD = 0.5
    nlu_config_module.DEFAULT_MODEL_DIR = Path("unused")
    nlu_config_module.MODEL_NAME = "structure_b_item_query_decoder"
    sys.modules["nlu"] = nlu_module
    sys.modules["nlu.config"] = nlu_config_module
