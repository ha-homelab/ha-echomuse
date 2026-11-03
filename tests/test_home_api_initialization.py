"""Exercise base initialization without importing a Home Assistant runtime."""

import ast
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import unittest


COMPONENT = Path(__file__).resolve().parents[1] / "custom_components/echomuse_home/__init__.py"


def home_api_class(base):
    """Load the real class against only the external API's constructor contract.

    The full registered acquisition and authorization path is exercised by
    runtime_home_tools.py with Home Assistant, not emulated here.
    """
    source = ast.parse(COMPONENT.read_text(), filename=str(COMPONENT))
    declaration = next(node for node in source.body
                       if isinstance(node, ast.ClassDef) and node.name == "HomeAPI")
    module = ast.Module(body=[declaration], type_ignores=[])
    namespace = {"llm": SimpleNamespace(API=base), "DOMAIN": "echomuse_home"}
    exec(compile(module, str(COMPONENT), "exec"), namespace)
    return namespace["HomeAPI"]


class HomeAPIInitializationTest(unittest.TestCase):
    def test_current_slotted_api_defaults_are_initialized(self):
        @dataclass(slots=True, kw_only=True)
        class API:
            hass: object
            id: str
            name: str
            requires_admin: bool = False

        hass = object()
        api = home_api_class(API)(hass, {"control_entities": ["light.fixture"], "aliases": {}})
        self.assertIs(api.requires_admin, False)
        self.assertIs(api.hass, hass)
        self.assertEqual(api.id, "echomuse_home")
        self.assertEqual(api.name, "EchoMuse local home control and statistics")
        self.assertEqual(api.controls, {"light.fixture"})

    def test_older_api_without_admin_keyword_remains_supported(self):
        @dataclass(slots=True, kw_only=True)
        class API:
            hass: object
            id: str
            name: str

        hass = object()
        api = home_api_class(API)(hass, {"control_entities": [], "aliases": {}})
        self.assertIs(api.hass, hass)
        self.assertEqual(api.controls, set())


if __name__ == "__main__":
    unittest.main()
