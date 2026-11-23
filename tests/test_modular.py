import json, re, unittest
from pathlib import Path

class ModularTests(unittest.TestCase):
    def test_mcu_control_and_parameters_keep_original_tokens(self):
        root = Path(__file__).resolve().parents[1]
        expected = json.loads((root/'docs/mspm0-refactor-tokens.json').read_text(encoding='utf-8'))
        def tokens(text):
            return re.sub(r'\s+', '', re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S))
        settings = tokens((root/'mspm0/app_settings.h').read_text(encoding='utf-8'))
        control = tokens((root/'mspm0/ball_control.c').read_text(encoding='utf-8'))
        for name, value in expected.items():
            self.assertIn(value, settings if name == 'settings' else control, name)

    def test_function_modules_share_existing_public_types(self):
        from ball_balance.capture import Frame
        from ball_balance.inference import InferenceResult
        from ball_balance.serial_link import SerialSender
        from ball_balance.runtime import Frame as OriginalFrame
        self.assertIs(Frame, OriginalFrame)
        self.assertTrue(callable(SerialSender.send_once))
        self.assertTrue(hasattr(InferenceResult, '__dataclass_fields__'))
