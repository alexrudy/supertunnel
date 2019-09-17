from . import command


def test_base_group(invoke):
    _, args = invoke(command.main, ["run"])
    assert args[0] == "ssh"
    assert "BatchMode yes" in args


def test_forward(invoke):
    _, args = invoke(command.main, ["forward", "-p80:90", "example.com"])
    assert args[-3:-1] == ["-L", "80:localhost:90"]
