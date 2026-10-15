"""
SolidWorks Document Operations
------------------------------
Create, open, save, and manage SolidWorks documents.
"""

import os
import logging
import traceback
from contextlib import nullcontext
from typing import Optional, Dict

import win32com.client
import pythoncom

from ..constants import SwErrors, SwDocumentTypes, SwFileTypes
from ..utils import find_template
from ..native_fault import native_hresult

logger = logging.getLogger(__name__)


class DocumentOperations:
    """
    Mixin class for document operations
    
    Requires parent class to have:
    - self._sw_app: SolidWorks application object
    - self.is_connected: Connection status property
    - self.connect(): Connection method
    - self._result(): Result factory method
    - self._units: UnitConverter instance
    """

    def create_recovery_snapshot(self,directory: str,filepath: Optional[str]=None) -> Dict:
        """Explicit private part copy or experimental assembly/drawing package."""
        if not self.is_connected:
            return self._result(False,'Connect to the configured PID before creating a recovery snapshot',
                                SwErrors.swConnectionError,{'configured_pid':self._target_pid})
        try:
            from ..recovery_snapshot import snapshot_part
            pid=int(self._target_pid)
            revision=self._sw_app.RevisionNumber
            revision=revision() if callable(revision) else revision
            major=int(str(revision).split('.')[0])
            module=win32com.client.gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,major,0)
            app=module.ISldWorks(self._sw_app._oleobj_)
            adapter=lambda doc:module.IModelDoc2(doc._oleobj_)
            if filepath is not None:
                from pathlib import Path
                from ..recovery_snapshot import get0
                requested=Path(filepath)
                if not filepath or not requested.is_absolute():
                    raise ValueError('Background recovery requires an absolute already-open part path')
                document=app.GetOpenDocumentByName(str(requested))
                if document is None:
                    raise ValueError('Background recovery source is not open in the configured PID; no document was opened')
                model=adapter(document)
                if Path(str(get0(model,'GetPathName'))).resolve()!=requested.resolve():
                    raise ValueError('Background recovery source path mismatch')
                if int(get0(model,'GetType'))!=1:
                    raise ValueError('Background recovery currently supports parts only')
                result=snapshot_part(app,pid,directory,adapter,document=document)
                return self._result(True,'Created private background part recovery snapshot',data=result)
            active=app.ActiveDoc
            if active is not None and adapter(active).GetType() in (2,3):
                from ..assembly_recovery import snapshot_package
                from ..package_repair_service import configured_processor
                result=snapshot_package(app,pid,directory,adapter,package_processor=configured_processor())
            else:
                result=snapshot_part(app,pid,directory,adapter)
            return self._result(True,'Created private recovery snapshot',data=result)
        except Exception as exc:
            return self._result(False,f'Recovery snapshot failed: {exc}',SwErrors.swFileSaveError,
                                getattr(exc,'data',{'configured_pid':self._target_pid}))
    
    def create_new_part(self) -> Dict:
        """
        Create a new part document
        
        Returns:
            Result dictionary with document info
        """
        try:
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            # Find part template
            template = find_template("part")
            if not template:
                template = ""  # Let SolidWorks use default
                logger.info("Using SolidWorks default part template")
            else:
                logger.info(f"Using template: {template}")
            
            # Create document
            doc = self._sw_app.NewDocument(template, 0, 0, 0)
            
            if doc is None:
                return self._result(False, "Failed to create part document",
                                  SwErrors.swFileLoadError)
            
            # Set view
            try:
                doc.ShowNamedView2("*Isometric", 7)
                doc.ViewZoomtofit2()
            except:
                pass
            
            title = self._get_doc_title(doc)
            
            return self._result(True, f"Created part: {title}",
                              SwErrors.swSuccess,
                              {"name": title, "type": "Part"})
            
        except Exception as e:
            logger.error(f"Create part error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
    
    def create_new_assembly(self) -> Dict:
        """
        Create a new assembly document
        
        Returns:
            Result dictionary with document info
        """
        try:
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            template = find_template("assembly")
            if not template:
                template = ""
            
            doc = self._sw_app.NewDocument(template, 0, 0, 0)
            
            if doc is None:
                return self._result(False, "Failed to create assembly",
                                  SwErrors.swFileLoadError)
            
            try:
                doc.ShowNamedView2("*Isometric", 7)
                doc.ViewZoomtofit2()
            except:
                pass
            
            title = self._get_doc_title(doc)
            
            return self._result(True, f"Created assembly: {title}",
                              SwErrors.swSuccess,
                              {"name": title, "type": "Assembly"})
            
        except Exception as e:
            logger.error(f"Create assembly error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
    
    def create_new_drawing(self, paper_size: str = "A4") -> Dict:
        """
        Create a new drawing document
        
        Args:
            paper_size: Paper size (A4, A3, A2, A1, Letter)
        
        Returns:
            Result dictionary with document info
        """
        try:
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            template = find_template("drawing")
            if not template:
                template = ""
            
            doc = self._sw_app.NewDocument(template, 0, 0, 0)
            
            if doc is None:
                return self._result(False, "Failed to create drawing",
                                  SwErrors.swFileLoadError)
            
            title = self._get_doc_title(doc)
            
            return self._result(True, f"Created drawing: {title}",
                              SwErrors.swSuccess,
                              {"name": title, "type": "Drawing", "paper_size": paper_size})
            
        except Exception as e:
            logger.error(f"Create drawing error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
    
    def open_document(self, filepath: str, memory_warning_action: str = 'manual') -> Dict:
        """
        Open an existing document
        
        Args:
            filepath: Path to SolidWorks file
        
        Returns:
            Result dictionary
        """
        try:
            if memory_warning_action not in ('manual', 'continue', 'cancel'):
                return self._result(False, 'Invalid memory_warning_action', SwErrors.swFileLoadError)
            if memory_warning_action != 'manual' and not self._target_pid:
                return self._result(False, 'Automatic warning handling requires SOLIDWORKS_TARGET_PID',
                                    SwErrors.swFileLoadError)
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            if not os.path.exists(filepath):
                return self._result(False, f"File not found: {filepath}",
                                  SwErrors.swFileNotFoundError)
            
            # Determine document type from extension
            ext = os.path.splitext(filepath)[1].lower()
            type_map = {
                ".sldprt": SwDocumentTypes.swDocPART,
                ".sldasm": SwDocumentTypes.swDocASSEMBLY,
                ".slddrw": SwDocumentTypes.swDocDRAWING,
            }
            doc_type = type_map.get(ext, SwDocumentTypes.swDocPART)
            
            # Open document
            errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            
            handler = None
            if memory_warning_action != 'manual':
                from .memory_warning import MemoryWarningHandler
                actual_pid = self._sw_app.GetProcessID
                actual_pid = actual_pid() if callable(actual_pid) else actual_pid
                if actual_pid != int(self._target_pid):
                    return self._result(False, 'Target PID changed', SwErrors.swFileLoadError)
                handler = MemoryWarningHandler(actual_pid, memory_warning_action)
            with handler if handler is not None else nullcontext():
                doc = self._sw_app.OpenDoc6(filepath, int(doc_type), 0, "", errors, warnings)

            handling = {'memory_warning_events': handler.events,
                        'memory_warning_handler_errors': handler.errors} if handler else {}

            # SolidWorks can return a document even after No dismisses its
            # resource warning. Do not authorize downstream rebuild/save work
            # merely because OpenDoc6 returned a COM object in that case.
            if handler and memory_warning_action == 'cancel' and handler.events:
                handling['document_returned'] = doc is not None
                handling['operation_cancelled'] = True
                return self._result(False,
                    'Opening cancelled after a low-memory warning. SolidWorks may have '
                    'loaded documents; inspect this PID before further CAD operations.',
                    SwErrors.swFileLoadError, handling)
            if handler and handler.errors:
                return self._result(False,
                    'Memory warning handler failed; opening could not be verified safely.',
                    SwErrors.swFileLoadError, handling)
            
            if doc is None or errors.value != 0:
                return self._result(False, f"Failed to open (error {errors.value})",
                                  SwErrors.swFileLoadError, handling)
            
            title = self._get_doc_title(doc)
            
            return self._result(True, f"Opened: {title}",
                              SwErrors.swSuccess,
                              {"name": title, "path": filepath, **handling})
            
        except Exception as e:
            logger.error(f"Open document error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
    
    def save_document(self, filepath: str = None) -> Dict:
        """
        Save the active document
        FIXED v4.1: Use doc.SaveAs() as primary method (avoids COM type mismatch
        with Extension.SaveAs where None parameter fails in SW 2025).
        
        Args:
            filepath: Path to save (None = save in place)
        
        Returns:
            Result dictionary
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            if filepath:
                # Ensure absolute path
                filepath = os.path.abspath(filepath)
                
                # Ensure directory exists
                dir_path = os.path.dirname(filepath)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path)
                
                saved = False
                method_used = ""
                
                # Method 1: doc.SaveAs (simplest, most reliable for SW 2025)
                try:
                    result = doc.SaveAs(filepath)
                    if result:
                        saved = True
                        method_used = "SaveAs"
                except Exception as e:
                    if native_hresult(e) is not None:
                        raise
                    logger.debug(f"doc.SaveAs failed: {e}")
                
                # Method 2: Extension.SaveAs with proper VARIANT null dispatch
                if not saved:
                    try:
                        empty_export = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
                        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                        
                        result = doc.Extension.SaveAs(
                            filepath, 0, 0, empty_export, errors, warnings
                        )
                        if result and errors.value == 0:
                            saved = True
                            method_used = "Extension.SaveAs"
                    except Exception as e:
                        if native_hresult(e) is not None:
                            raise
                        logger.debug(f"Extension.SaveAs failed: {e}")
                
                # Method 3: Extension.SaveAs2
                if not saved:
                    try:
                        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                        
                        result = doc.Extension.SaveAs2(
                            filepath, 0, 0, None, "", False, errors, warnings
                        )
                        if result:
                            saved = True
                            method_used = "Extension.SaveAs2"
                    except Exception as e:
                        if native_hresult(e) is not None:
                            raise
                        logger.debug(f"Extension.SaveAs2 failed: {e}")
                
                if not saved:
                    return self._result(False, "Save failed - all methods attempted",
                                      SwErrors.swFileSaveError)
                
                return self._result(True, f"Saved: {filepath} [{method_used}]",
                                  SwErrors.swSuccess,
                                  {"path": filepath, "method": method_used})
            else:
                # Save in place
                result = doc.Save3(0, 0, 0)
                
                if result != 0:
                    return self._result(False, f"Save failed (code {result})",
                                      SwErrors.swFileSaveError)
                
                path = self._get_doc_path(doc)
                return self._result(True, f"Saved: {path}",
                                  SwErrors.swSuccess, {"path": path})
            
        except Exception as e:
            logger.error(f"Save error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileSaveError)
    
    def close_document(self, save: bool = False) -> Dict:
        """
        Close the active document
        
        Args:
            save: Save before closing
        
        Returns:
            Result dictionary
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return self._result(True, "No document to close")
            
            title = self._get_doc_title(doc)
            
            if save:
                doc.Save3(0, 0, 0)
            
            self._sw_app.CloseDoc(title)
            
            return self._result(True, f"Closed: {title}",
                              SwErrors.swSuccess, {"document": title})
            
        except Exception as e:
            logger.error(f"Close error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
    
    def get_document_info(self) -> Dict:
        """
        Get information about the active document
        
        Returns:
            Result dictionary with document details
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            type_names = {
                0: "None",
                1: "Part",
                2: "Assembly",
                3: "Drawing"
            }
            
            doc_type = doc.GetType()
            title = self._get_doc_title(doc)
            path = self._get_doc_path(doc)
            
            info = {
                "title": title,
                "path": path if path else "Not saved",
                "type": type_names.get(doc_type, "Unknown"),
                "type_code": doc_type,
            }
            
            return self._result(True, f"{title} ({info['type']})",
                              SwErrors.swSuccess, info)
            
        except Exception as e:
            logger.error(f"Get info error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
    
    def list_open_documents(self) -> Dict:
        """
        List all open documents
        
        Returns:
            Result dictionary with document list
        """
        try:
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            docs = []
            doc = self._sw_app.GetFirstDocument()
            
            while doc:
                try:
                    title = doc.GetTitle
                    if callable(title):
                        title = title()
                    doc_type = doc.GetType()
                    
                    type_names = {1: "Part", 2: "Assembly", 3: "Drawing"}
                    
                    docs.append({
                        "title": title,
                        "type": type_names.get(doc_type, "Unknown")
                    })
                except:
                    pass
                
                doc = doc.GetNext()
            
            return self._result(True, f"{len(docs)} document(s) open",
                              SwErrors.swSuccess, {"documents": docs})
            
        except Exception as e:
            logger.error(f"List documents error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
