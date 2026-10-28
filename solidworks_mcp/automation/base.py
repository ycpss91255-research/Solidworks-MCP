"""
SolidWorks Automation Base
--------------------------
Core automation class with connection management and utility methods.
"""

import os
import time
import logging
import datetime
import traceback
import sys
from typing import Optional, Dict, Any, Tuple

# COM imports
import win32com.client
import pythoncom

from ..constants import SwErrors, SwPlanes, SwDocumentTypes, SwViews
from ..config import get_config
from ..utils import UnitConverter, find_solidworks, find_template

logger = logging.getLogger(__name__)


class SolidWorksAutomation:
    """
    Core SolidWorks automation class
    
    Handles connection management, document operations, and provides
    utility methods for all automation tasks.
    """
    
    def __init__(self):
        """Initialize automation instance"""
        from ..com_safety import install_dependency_query_guard
        install_dependency_query_guard()
        from ..com_keepalive import install_feature_reference_keeper
        install_feature_reference_keeper()
        self._sw_app = None
        self._connected = False
        self._config = get_config()
        self._units = UnitConverter(self._config.default_unit)
        self._sw_exe_path = None
        # Keep the requested identity for the lifetime of this MCP instance.
        self._target_pid = os.environ.get("SOLIDWORKS_TARGET_PID")
        self._configured_target = self._target_pid
        self._auto_launch = os.environ.get('SOLIDWORKS_AUTO_LAUNCH') == '1'
        self._target_com_initialized = False
        self._recovery_startup_enabled = os.environ.get('SOLIDWORKS_RECOVERY_MONITOR') != '0'
        self._recovery_monitor_error = None
        self._recovery_worker = None
        self._journal_warning_handler = None
        self._bound_identity = None
        self._native_fault = None
        
        logger.info("SolidWorksAutomation initialized")
    
    def release_idle_com_references(self) -> bool:
        """Release held IFeature wrappers once no document is open (read-only query)."""
        if self.native_fault_result() is not None:
            return False
        from ..com_keepalive import release_if_no_documents
        return release_if_no_documents(self._sw_app)

    # ========================================================================
    # Properties
    # ========================================================================
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to SolidWorks"""
        if self.native_fault_result() is not None:
            return False
        if not self._connected or self._sw_app is None:
            return False
        if getattr(self, '_bound_identity', None):
            from .managed_session import process_identity
            try:
                if process_identity(int(self._target_pid)) is None:
                    self._connected = False
                    self._sw_app = None
                    return False
            except Exception:
                return False  # Unknown OS identity is not permission to probe COM.
        
        try:
            # Test connection by accessing a property
            _ = self._sw_app.RevisionNumber
            return True
        except Exception as exc:
            if self.record_native_failure(exc) is not None:
                return False
            try:
                # Some versions use method instead of property
                _ = self._sw_app.RevisionNumber()
                return True
            except Exception as exc:
                if self.record_native_failure(exc) is not None:
                    return False
                self._connected = False
                self._sw_app = None
                return False
    
    @property
    def units(self) -> UnitConverter:
        """Get unit converter"""
        return self._units
    
    @property
    def app(self):
        """Get SolidWorks application object"""
        return self._sw_app
    
    # ========================================================================
    # Result Helper
    # ========================================================================
    
    def _fault_store_instance(self):
        from ..native_fault import FaultStore
        if getattr(self, '_fault_store', None) is None:
            self._fault_store = FaultStore()
        return self._fault_store

    def record_native_failure(self, error):
        """No CAD calls: retain identity-bound evidence before any later request."""
        from ..native_fault import native_hresult
        hresult = native_hresult(error)
        if hresult is None or self._target_pid is None:
            return None
        pid = int(self._target_pid)
        fault = {'pid': pid, 'start_time': getattr(self, '_bound_identity', None),
                 'hresult': hresult, 'message': str(error)}
        self._native_fault = fault
        self._connected = False
        try:
            fault = self._fault_store_instance().record(pid, fault['start_time'], error)
            self._native_fault = fault
        except Exception as exc:
            fault['persistence_error'] = str(exc)
            logger.error('Native fault marker could not be persisted: %s', exc)
        return fault

    def native_fault_result(self):
        """Block known faulted identities before COM, including recovery probes."""
        if self._target_pid is None:
            return None
        from .managed_session import process_identity
        try:
            pid = int(self._target_pid)
            fault = getattr(self, '_native_fault', None)
            if fault and fault['pid'] == pid:
                if process_identity(pid) is None:
                    self._native_fault = None
                    self._connected = False
                    self._sw_app = None
                    return None  # Existing managed startup handles an exited target.
            else:
                fault = self._fault_store_instance().read(pid, process_identity)
            if fault is None:
                return None
            self._native_fault = fault
            message = f'CAD calls to faulted SolidWorks PID {pid} are stopped. Preserve evidence and retire this process; reconnect only after an owned replacement is available.'
            data = {'configured_pid': pid, 'native_fault_quarantined': True, 'native_fault': fault}
        except Exception as exc:
            message = f'Cannot verify native fault state for PID {self._target_pid}: {exc}. No CAD call was made.'
            data = {'configured_pid': self._target_pid, 'native_fault_state_unverified': True}
        return self._result(False, message, SwErrors.swConnectionError, data)

    def _result(self, success: bool, message: str,
                error_code: SwErrors = SwErrors.swSuccess,
                data: Optional[Dict] = None) -> Dict:
        """
        Create standardized result dictionary
        
        Args:
            success: Operation success status
            message: Human-readable message
            error_code: Error code enum
            data: Optional additional data
        
        Returns:
            Standardized result dictionary
        """
        if not success:
            error = sys.exc_info()[1]
            fault = self.record_native_failure(error) if error is not None else None
            if fault is not None:
                data = dict(data or {}, native_fault_quarantined=True, native_fault=fault)
        result = {
            "success": success,
            "message": message,
            "error_code": int(error_code),
            "error_name": error_code.name,
            "timestamp": datetime.datetime.now().isoformat()
        }
        if data:
            result["data"] = data
        return result
    
    # ========================================================================
    # Connection Methods
    # ========================================================================

    def _connect_target(self) -> Dict:
        """Attach only to the requested ROT entry; never launch or fall back."""
        blocked = self.native_fault_result()
        if blocked is not None:
            return blocked
        self._sw_app = None
        self._connected = False
        try:
            pid = int(self._target_pid)
            if pid <= 0:
                raise ValueError("SOLIDWORKS_TARGET_PID must be positive")
            from .managed_session import process_identity
            self._bound_identity = process_identity(pid)
            if not self._target_com_initialized:
                pythoncom.CoInitialize()
                self._target_com_initialized = True
            try:
                rot = pythoncom.GetRunningObjectTable()
                context = pythoncom.CreateBindCtx(0)
                for moniker in rot.EnumRunning():
                    if moniker.GetDisplayName(context, None) != f"SolidWorks_PID_{pid}":
                        continue
                    obj = rot.GetObject(moniker)
                    app = win32com.client.Dispatch(
                        obj.QueryInterface(pythoncom.IID_IDispatch))
                    actual_pid = app.GetProcessID
                    if callable(actual_pid):
                        actual_pid = actual_pid()
                    if int(actual_pid) != pid:
                        raise RuntimeError("SolidWorks process identity mismatch")
                    version = app.RevisionNumber
                    if callable(version):
                        version = version()
                    self._sw_app = app
                    self._connected = True
                    logger.info("Connected to SolidWorks PID %s", pid)
                    return self._result(True, f"Connected to SolidWorks PID {pid}",
                                        data={"pid": pid, "version": str(version),
                                              "launched": False})
                raise RuntimeError(f"SolidWorks PID {pid} is not available in ROT")
            finally:
                if not self._connected:
                    pythoncom.CoUninitialize()
                    self._target_com_initialized = False
        except Exception as exc:
            return self._result(False, f"Target connection failed: {exc}",
                                SwErrors.swConnectionError)
    
    def _ensure_journal_warning_hook(self):
        from .journal_warning import JournalWarningHandler
        from .managed_session import process_identity
        action = os.environ.get('SOLIDWORKS_JOURNAL_WARNING_ACTION', 'manual')
        if action not in ('manual', 'dismiss'):
            raise ValueError('SOLIDWORKS_JOURNAL_WARNING_ACTION must be manual or dismiss')
        current = getattr(self, '_journal_warning_handler', None)
        pid = int(self._target_pid)
        if current and action == 'dismiss' and current.pid == pid and current.thread.is_alive():
            return current
        self._stop_journal_warning_hook()
        if action == 'manual':
            return None
        identity = process_identity(pid)
        if identity is None:
            raise RuntimeError(f'Journal warning target PID {pid} has exited')
        handler = JournalWarningHandler(pid, timeout=None)
        handler.__enter__()
        if process_identity(pid) != identity:
            handler.__exit__(None, None, None)
            raise RuntimeError(f'Journal warning target PID {pid} changed')
        self._journal_warning_handler = handler
        return handler

    def _stop_journal_warning_hook(self):
        handler = getattr(self, '_journal_warning_handler', None)
        if handler:
            handler.__exit__(None, None, None)
            self._journal_warning_handler = None

    def connect(self) -> Dict:
        """Connect only to an explicitly configured, already running PID."""
        blocked = self.native_fault_result()
        if blocked is not None:
            return blocked
        if self._auto_launch:
            try:
                from .managed_session import connect_managed
                result = connect_managed(self)
            except Exception as exc:
                self._stop_journal_warning_hook()
                return self._result(False, f'Managed connection failed: {exc}',
                                    SwErrors.swConnectionError)
        elif self._target_pid is None:
            return self._result(False,
                'SOLIDWORKS_TARGET_PID is required. No SolidWorks process was launched. '
                'Configure the intended running PID and restart the MCP connection.',
                SwErrors.swConnectionError)
        else:
            try:
                self._ensure_journal_warning_hook()
                result = self._connect_target()
            except Exception as exc:
                result = self._result(False, f'Target connection failed: {exc}', SwErrors.swConnectionError)
        if not result['success']:
            self._stop_journal_warning_hook()
        handler = getattr(self, '_journal_warning_handler', None)
        if handler:
            result.setdefault('data', {})['journal_warning_hook'] = {
                'pid': handler.pid, 'running': handler.thread.is_alive(),
                'events': handler.events, 'errors': handler.errors}
        if result['success'] and getattr(self,'_recovery_startup_enabled',False):
            self._recovery_monitor_error = None
            self._recovery_worker = None
            try:
                from ..recovery_service import ensure_recovery_worker
                recovery = ensure_recovery_worker(result['data']['pid'],app=self.app)
                self._recovery_worker = recovery
                if recovery is not None: result['data']['recovery_monitor'] = recovery
            except Exception as exc:
                self._recovery_monitor_error = str(exc)
                result.setdefault('data', {})['recovery_monitor_error'] = str(exc)
                logger.warning('Configured recovery monitor did not start: %s', exc)
        return result

    def recovery_monitor_error(self):
        """Refresh recovery health for tool responses, with no startup side effects."""
        worker=getattr(self,'_recovery_worker',None)
        if worker is not None:
            from ..recovery_service import recovery_worker_error
            self._recovery_monitor_error=recovery_worker_error(self._target_pid,worker)
        return getattr(self,'_recovery_monitor_error',None)

    def disconnect(self) -> Dict:
        """
        Disconnect from SolidWorks (does not close SolidWorks)
        
        Returns:
            Result dictionary
        """
        self._stop_journal_warning_hook()
        self._sw_app = None
        self._connected = False
        if self._target_com_initialized:
            pythoncom.CoUninitialize()
            self._target_com_initialized = False
        logger.info("Disconnected from SolidWorks")
        return self._result(True, "Disconnected from SolidWorks")
    
    # ========================================================================
    # Document Methods
    # ========================================================================
    
    def get_active_doc(self) -> Tuple[Any, Optional[Dict]]:
        """
        Get active document with auto-connect
        
        Returns:
            Tuple of (document, error_result)
            - If successful: (document, None)
            - If failed: (None, error_dict)
        """
        if not self.is_connected:
            result = self.connect()
            if not result["success"]:
                return None, result
        
        doc = self._sw_app.ActiveDoc
        if doc is None:
            return None, self._result(False,
                "No document open. Use create_new_part first.",
                SwErrors.swNoActiveDocument)
        
        return doc, None
    
    def _get_doc_title(self, doc) -> str:
        """Get document title (handles property/method difference)"""
        try:
            title = doc.GetTitle
            if callable(title):
                return title()
            return title
        except:
            return "Unknown"
    
    def _get_doc_path(self, doc) -> str:
        """Get document path (handles property/method difference)"""
        try:
            path = doc.GetPathName
            if callable(path):
                return path()
            return path
        except:
            return ""
