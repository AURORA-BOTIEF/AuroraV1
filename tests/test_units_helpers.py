import importlib.util
import os


def load_module():
    path = os.path.join(os.path.dirname(__file__), "..", "CG-Backend", "lambda", "strands_ppt_generator", "strands_ppt_generator.py")
    path = os.path.abspath(path)
    spec = importlib.util.spec_from_file_location("strands_ppt_generator", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_emu_to_inches_and_back():
    mod = load_module()
    emu = mod.EMU_PER_INCH * 2.5
    inches = mod.emu_to_inches(emu)
    assert abs(inches - 2.5) < 1e-6
    back = mod.inches_to_emu(inches)
    # inches_to_emu returns int, allow small rounding
    assert abs(back - int(emu)) <= 1


def test_px_size_from_inches_float_and_object():
    mod = load_module()
    # float input
    assert mod.px_size_from_inches(1.0, dpi=100) == 100

    # object with .inches attribute
    class FakeLen:
        def __init__(self, v):
            self.inches = v

    fl = FakeLen(2.0)
    assert mod.px_size_from_inches(fl, dpi=75) == 150


def test_round_trip_small_values():
    mod = load_module()
    val_in = 0.125
    emu = mod.inches_to_emu(val_in)
    back = mod.emu_to_inches(emu)
    assert abs(back - val_in) < 1e-3
