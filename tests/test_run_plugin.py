import os
import shutil
import sys
import time
from typing import Any, List

import pytest

from porcupine import get_main_window, utils
from porcupine.plugins.run import no_terminal, settings, terminal


@pytest.fixture(autouse=True)
def isolated_history():
    assert not settings.get("run_history", List[Any])
    yield
    settings.set_("run_history", [])


@pytest.fixture
def fake_runner(tmp_path, monkeypatch):
    if sys.platform == "win32":
        path = tmp_path / "fake_runner.py"
        input_statement = "input()"
    else:
        path = tmp_path / "fake_runner.sh"
        input_statement = "read junk"

    shutil.copy(terminal.run_script, path)
    old_content = path.read_text()
    assert old_content.count(input_statement) == 1
    path.write_text(old_content.replace(input_statement, ""))

    monkeypatch.setattr("porcupine.plugins.run.terminal.run_script", path)


@pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS") == "true", reason="no external terminal on github actions"
)
def test_external_terminal(filetab, tmp_path, fake_runner, isolated_history, wait_until):
    filetab.textwidget.insert("end", "open('file', 'w').write('hello')")
    filetab.save_as(tmp_path / "hello.py")
    get_main_window().event_generate("<<Run:Repeat0>>")
    wait_until(lambda: (tmp_path / "file").exists() and (tmp_path / "file").read_text() == "hello")


def get_output_widget(filetab):
    return filetab.bottom_frame.nametowidget("run_output")


def get_output(filetab):
    return get_output_widget(filetab).get("1.0", "end - 1 char")


def test_output_in_porcupine_window(filetab, tmp_path, wait_until):
    filetab.textwidget.insert(
        "end",
        r"""
print("123")
print("örkki")

import sys

# Test error handling for badly printed bytes
# All bytes that are invalid utf-8 AND invalid cp1252: 81, 8D, 8F, 90, 9D
sys.stderr.buffer.write(b'\x81')
print()

# unicodes beyond U+FFFF are not supported by tk
# can't test this on windows because cp1252 doesn't go beyond U+FFFF
if sys.platform != "win32":
    print("\N{pile of poo}")
""",
    )
    filetab.save_as(tmp_path / "lol.py")
    no_terminal.run_command(f"{utils.quote(sys.executable)} lol.py", tmp_path)
    wait_until(lambda: "The process completed successfully." in get_output(filetab))

    assert "123" in get_output(filetab)
    assert "örkki" in get_output(filetab)
    if sys.platform == "win32":
        assert get_output(filetab).count("\N{replacement character}") == 1
    else:
        assert get_output(filetab).count("\N{replacement character}") == 2


def test_python_error_message(filetab, tabmanager, tmp_path, wait_until):
    (tmp_path / "asdf.py").write_text("print(1)\nopen('this does not exist')\nprint(2)\n")
    filetab.textwidget.insert("end", "import asdf")
    filetab.save_as(tmp_path / "main.py")

    no_terminal.run_command(f"{utils.quote(sys.executable)} main.py", tmp_path)
    wait_until(lambda: "The process failed with status 1." in get_output(filetab))
    assert "No such file or directory" in get_output(filetab)

    # click the last link
    textwidget = get_output_widget(filetab)
    textwidget.mark_set("current", "link.last - 1 char")
    no_terminal._no_terminal_runners[str(filetab)]._link_manager._open_link(None)

    selected_tab = tabmanager.select()
    assert selected_tab != filetab
    assert selected_tab.path == tmp_path / "asdf.py"
    assert selected_tab.textwidget.get("sel.first", "sel.last") == "open('this does not exist')"


def test_python_unbuffered(filetab, tmp_path, wait_until):
    (tmp_path / "sleeper.py").write_text(
        """
import time
print("This should show up immediately")
time.sleep(5)
"""
    )
    start = time.monotonic()
    no_terminal.run_command(f"{utils.quote(sys.executable)} sleeper.py", tmp_path)
    wait_until(lambda: "This should show up immediately" in get_output(filetab))
    end = time.monotonic()
    assert end - start < 3


def test_no_previous_command_error(filetab, tmp_path, mocker):
    filetab.save_as(tmp_path / "foo.txt")
    mock = mocker.patch("tkinter.messagebox.showerror")
    get_main_window().event_generate("<<Run:Repeat0>>")

    mock.assert_called_once()
    if filetab.tk.eval("tk windowingsystem") == "aqua":
        assert "press ⇧F5 to choose a command" in str(mock.call_args)
    else:
        assert "press Shift+F5 to choose a command" in str(mock.call_args)
    assert "then repeat it with F5" in str(mock.call_args)
