"""Verify real task-dialog handling against owned disposable helper processes."""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from solidworks_mcp.automation.memory_warning import MemoryWarningHandler
import win32gui
import win32process

root = Path(__file__).resolve().parents[1]
out = root / 'test-results/native-memory-warning'
out.mkdir(exist_ok=True)
(out / 'taskdialog.manifest').write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
<dependency><dependentAssembly><assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls"
version="6.0.0.0" processorArchitecture="*" publicKeyToken="6595b64144ccf1df" language="*"/>
</dependentAssembly></dependency></assembly>''', encoding='utf-8')
helpers = []
report = {'passed': False, 'cases': []}
def launch():
    process = subprocess.Popen([sys._base_executable, str(root/'tests/memory_warning_fixture.py'), str(out)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    helpers.append(process)
    return process
try:
    unrelated = launch()
    for action, expected in [('continue', 6), ('cancel', 7)]:
        target = launch()
        with MemoryWarningHandler(target.pid, action, timeout=8) as handler:
            try:
                stdout, stderr = target.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                def inspect(hwnd, _):
                    if win32process.GetWindowThreadProcessId(hwnd)[1] == target.pid:
                        print('TARGET', hwnd, win32gui.GetClassName(hwnd), win32gui.GetWindowText(hwnd), flush=True)
                    return True
                win32gui.EnumWindows(inspect, None)
                print('HANDLER', handler.events, handler.errors, flush=True)
                raise
            assert target.returncode == 0, stderr
            assert stdout.strip() == str(expected), (stdout, stderr)
            assert unrelated.poll() is None, 'Unrelated dialog was changed'
        assert handler.events, 'No handler event'
        report['cases'].append({'action': action, 'button': expected, 'events': handler.events,
                                'unrelated_process_untouched': True})
    report['passed'] = True
    print(json.dumps(report, indent=2))
finally:
    for process in helpers:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
    (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
