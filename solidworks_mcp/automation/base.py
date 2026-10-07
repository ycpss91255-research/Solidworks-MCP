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
        self._sw_app = None
        self._connected = False
        self._config = get_config()
        self._units = UnitConverter(self._config.default_unit)
        self._sw_exe_path = None
        # Keep the requested identity for the lifetime of this MCP instance.
        self._target_pid = os.environ.get("SOLIDWORKS_TARGET_PID")
        self._target_com_initialized = False
        
        logger.info("SolidWorksAutomation initialized")
    
    # ========================================================================
    # Properties
    # ========================================================================
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to SolidWorks"""
        if not self._connected or self._sw_app is None:
            return False
        
        try:
            # Test connection by accessing a property
            _ = self._sw_app.RevisionNumber
            return True
        except:
            try:
                # Some versions use method instead of property
                _ = self._sw_app.RevisionNumber()
                return True
            except:
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
        self._sw_app = None
        self._connected = False
        try:
            pid = int(self._target_pid)
            if pid <= 0:
                raise ValueError("SOLIDWORKS_TARGET_PID must be positive")
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
    
    def connect(self) -> Dict:
        """Connect only to an explicitly configured, already running PID."""
        if self._target_pid is None:
            return self._result(False,
                'SOLIDWORKS_TARGET_PID is required. No SolidWorks process was launched. '
                'Configure the intended running PID and restart the MCP connection.',
                SwErrors.swConnectionError)
        return self._connect_target()

    def disconnect(self) -> Dict:
        """
        Disconnect from SolidWorks (does not close SolidWorks)
        
        Returns:
            Result dictionary
        """
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
