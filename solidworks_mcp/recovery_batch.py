"""Sequential private copies of documents enumerated from one bound application."""
from .recovery_snapshot import get0,held_process,snapshot_part
from .assembly_recovery import document_state,snapshot_package
from .automation.managed_session import process_identity
from .native_fault import FaultStore,native_hresult
import traceback

def snapshot_documents(app,pid,directory,documents,adapter,allow_activation=False,idle=lambda:True):
    from .package_repair_service import configured_processor
    processor=configured_processor()
    with held_process(pid) as identity:
        report={'status':'writing','pid':pid,'process_start_time':identity,'document_type':'batch','snapshots':[]}
        def verify():
            if int(get0(app,'GetProcessID'))!=pid or process_identity(pid)!=identity:
                raise RuntimeError('Recovery batch target identity changed')
            if not idle():raise RuntimeError('Recovery batch interrupted by a command or dialog')
        try:
            for raw in documents:
                verify();doc=adapter(raw);kind=int(get0(doc,'GetType'))
                if kind==1:
                    snapshot=snapshot_part(app,pid,directory,adapter,document=raw)
                elif kind in (2,3):
                    original=get0(app,'ActiveDoc')
                    if original is None:raise RuntimeError('No active document to restore after package recovery')
                    before=document_state(adapter(original));target=document_state(doc)
                    def current():return document_state(adapter(get0(app,'ActiveDoc')))
                    def key(state):return (state['path'].casefold(),state['title'])
                    switching=key(before)!=key(target)
                    if switching and not allow_activation:
                        raise RuntimeError('Background package requires explicitly enabled API activation')
                    native_failed=False
                    try:
                        if switching:
                            # swDontRebuildActiveDoc=1. Never choose the prompt/rebuild modes.
                            app.ActivateDoc3(target['title'],False,1,0)
                            if key(current())!=key(target):raise RuntimeError('Recovery package activation selected another document')
                        snapshot=snapshot_package(app,pid,directory,adapter,
                            allow_step_activation=allow_activation,idle=idle,package_processor=processor)
                    except Exception as exc:
                        native_failed=native_hresult(exc) is not None
                        raise
                    finally:
                        if not native_failed:
                            verify()
                            if switching:
                                active=current()
                                if key(active)==key(target):app.ActivateDoc3(before['title'],False,1,0)
                                elif key(active)!=key(before):
                                    raise RuntimeError('Active document changed externally; previous view was not forced')
                                if current()!=before:raise RuntimeError('Original active document state was not restored')
                    snapshot['temporary_api_activation']=switching
                    snapshot['original_active_restored']=True
                else:raise RuntimeError('Recovery batch contains an unsupported document')
                verify()
                if snapshot.get('status')!='complete' or snapshot.get('pid')!=pid or snapshot.get('process_start_time')!=identity:
                    raise RuntimeError('Recovery batch contains an incomplete or foreign snapshot')
                report['snapshots'].append(snapshot)
            if not report['snapshots']:raise RuntimeError('Recovery batch has no selected documents')
            report['status']='complete'
            return {'success':True,'data':report}
        except Exception as exc:
            report.update(status='failed',error=str(exc),error_traceback=traceback.format_exc())
            hresult=native_hresult(exc)
            if hresult is not None:
                report['native_hresult']=hresult
                try:report['native_fault']=FaultStore().record(pid,identity,exc)
                except Exception as persistence_error:report['native_fault_persistence_error']=str(persistence_error)
            return {'success':False,'message':str(exc),'data':report}
