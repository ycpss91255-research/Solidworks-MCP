"""Settings that must match before reusing a persistent recovery worker."""
import os

def recovery_settings(interval):
    return {'interval_seconds':float(interval),
            'assemblies':os.environ.get('SOLIDWORKS_RECOVERY_ASSEMBLIES')=='1',
            'drawings':os.environ.get('SOLIDWORKS_RECOVERY_DRAWINGS')=='1',
            'all_documents':os.environ.get('SOLIDWORKS_RECOVERY_ALL_DOCUMENTS')=='1',
            'background_activation':os.environ.get('SOLIDWORKS_RECOVERY_BACKGROUND_ACTIVATION')=='1'}
