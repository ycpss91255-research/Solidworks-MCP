"""Persist native/RPC failure evidence by PID and process creation identity."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import msvcrt
import os
from pathlib import Path


NATIVE_HRESULTS = {0x80010105, 0x80010108, 0x800706BE, 0x800706BF}


def native_hresult(error):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        value = getattr(error, 'hresult', None)
        if isinstance(value, int) and value & 0xffffffff in NATIVE_HRESULTS:
            return (value & 0xffffffff) - 0x100000000
        error = getattr(error, '__cause__', None)
    return None


class FaultStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else Path.home() / '.solidworks-mcp' / 'native-faults'
        if not self.directory.is_absolute():
            raise ValueError('Native fault state directory must be absolute')

    def _path(self, pid):
        if isinstance(pid, bool) or int(pid) <= 0:
            raise ValueError('Native fault PID must be positive')
        return self.directory / f'pid-{int(pid)}.json'

    def _load(self, path, pid):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None
        if (not isinstance(value, dict) or value.get('kind') != 'solidworks_native_fault'
                or value.get('pid') != int(pid) or not isinstance(value.get('start_time'), str)
                or not value['start_time'] or not isinstance(value.get('hresult'), int)
                or value['hresult'] & 0xffffffff not in NATIVE_HRESULTS):
            raise ValueError('Native fault marker identity/schema is invalid')
        return value

    def read(self, pid, identity_reader):
        value = self._load(self._path(pid), pid)
        if value is None:
            return None
        return value if identity_reader(int(pid)) == value['start_time'] else None

    @contextmanager
    def _lock(self, path):
        with path.with_suffix('.lock').open('a+b') as stream:
            if stream.seek(0, 2) == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def record(self, pid, identity, error):
        hresult = native_hresult(error)
        if hresult is None:
            return None
        if not isinstance(identity, str) or not identity:
            raise ValueError('A known process creation identity is required')
        path = self._path(pid)
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._lock(path):
            previous = self._load(path, pid)
            if previous and previous['start_time'] == identity:
                return previous
            value = {'kind': 'solidworks_native_fault', 'pid': int(pid), 'start_time': identity,
                     'hresult': hresult, 'message': str(error), 'reporter_pid': os.getpid(),
                     'recorded_at': datetime.now(timezone.utc).isoformat()}
            temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
            try:
                temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            return value
