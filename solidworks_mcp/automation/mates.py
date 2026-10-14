"""Explicit feature replacement; never convert an existing mate's kind in place."""
import math
import logging
from pathlib import Path

from win32com.client import gencache

from ..constants import SwErrors


def _features(doc, types):
    found = {}
    raw = doc.FirstFeature()
    while raw:
        feature = types.IFeature(raw._oleobj_)
        found.setdefault(feature.Name, []).append(feature)
        if feature.GetTypeName2() == 'MateGroup':
            sub = feature.GetFirstSubFeature()
            while sub:
                item = types.IFeature(sub._oleobj_)
                found.setdefault(item.Name, []).append(item)
                sub = item.GetNextSubFeature()
        raw = feature.GetNextFeature()
    return found


class MateOperations:
    def recreate_distance_mate_as_limit(self, filepath, mate_name,
                                       minimum_m, maximum_m, distance_m,
                                       allow_identity_change=False):
        """Delete/recreate one ordinary distance mate. Leaves changes unsaved.

        Preflight failures leave geometry untouched. A later failure can leave a
        deleted or newly created feature, which is reported without retry/rollback.
        """
        state = {'original_deleted': False, 'replacement_created': False,
                 'saved': False, 'feature_identity_changed': False}
        try:
            if allow_identity_change is not True:
                raise ValueError('allow_identity_change=true is required; downstream feature references may change')
            if not Path(filepath).is_absolute() or not mate_name:
                raise ValueError('An absolute open assembly path and exact mate name are required')
            bounds = (minimum_m, maximum_m, distance_m)
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                   not math.isfinite(v) for v in bounds):
                raise ValueError('Distances must be finite numbers in meters')
            if not 0 <= minimum_m <= distance_m <= maximum_m:
                raise ValueError('Require 0 <= minimum_m <= distance_m <= maximum_m')
            if not self._connected or self._sw_app is None or not self._target_pid:
                raise ValueError('Connect to the configured PID first; this tool never launches SolidWorks')
            app = self._sw_app
            pid_value = app.GetProcessID
            if (pid_value() if callable(pid_value) else pid_value) != int(self._target_pid):
                raise ValueError('Connected PID differs from the configured target')
            revision = app.RevisionNumber
            revision = revision() if callable(revision) else revision
            types = gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}',
                                         0, int(revision.split('.')[0]), 0)
            app = types.ISldWorks(app._oleobj_)
            raw = app.GetOpenDocumentByName(str(Path(filepath)))
            if not raw:
                raise ValueError('Assembly must already be open in the configured PID')
            doc = types.IModelDoc2(raw._oleobj_)
            if doc.GetType() != 2 or Path(doc.GetPathName()) != Path(filepath):
                raise ValueError('Open document does not match the requested assembly')
            matches = _features(doc, types).get(mate_name, [])
            if len(matches) != 1 or matches[0].GetTypeName2() != 'MateDistanceDim':
                raise ValueError('Require exactly one ordinary MateDistanceDim with this name')
            old = matches[0]
            definition = types.IDistanceMateFeatureData(old.GetDefinition()._oleobj_)
            if definition.IsAdvancedMate:
                raise ValueError('Mate is already advanced')
            mate = types.IMate2(old.GetSpecificFeature2()._oleobj_)
            if mate.GetMateEntityCount() != 2:
                raise ValueError('Require exactly two selectable mate endpoints')
            references = [types.IMateEntity2(mate.MateEntity(i)._oleobj_).Reference
                          for i in range(2)]
            alignment, flip = mate.Alignment, definition.FlipDimension
            if not app.ActivateDoc3(doc.GetTitle(), False, 0, 0)[0]:
                raise ValueError('Could not activate requested assembly')
            manager = types.ISelectionMgr(doc.SelectionManager._oleobj_)
            selection = types.ISelectData(manager.CreateSelectData()._oleobj_)
            selection.Mark = 1

            def select_endpoints():
                doc.ClearSelection2(True)
                for reference in references:
                    if not reference.Select4(True, selection):
                        raise ValueError('Could not select a mate endpoint')
                if manager.GetSelectedObjectCount2(1) != 2:
                    raise ValueError('Expected exactly two selected mate endpoints')

            select_endpoints()  # Validate endpoints before deletion.
            doc.ClearSelection2(True)
            if not old.Select2(False, 0) or not doc.Extension.DeleteSelection2(0):
                raise ValueError('Original mate was not deleted')
            state.update(original_deleted=True, feature_identity_changed=True)
            del old, matches, mate, definition
            select_endpoints()
            before = set(_features(doc, types))
            assembly = types.IAssemblyDoc(doc._oleobj_)
            created = assembly.AddMate5(5, alignment, flip, distance_m, maximum_m,
                                       minimum_m, 0, 0, 0, 0, 0, False, False, 0, 0)
            if not created[0] or created[1] != 1:
                raise ValueError(f'AddMate5 failed: status {created[1]}')
            state['replacement_created'] = True
            new = [f for name, fs in _features(doc, types).items() if name not in before
                   for f in fs if f.GetTypeName2() == 'MateLimitDistanceDim']
            if len(new) != 1:
                raise ValueError('Could not identify exactly one new limit mate')
            feature = new[0]
            feature.Name = mate_name
            fresh = types.IDistanceMateFeatureData(feature.GetDefinition()._oleobj_)
            if (feature.Name != mate_name or not fresh.IsAdvancedMate or
                    any(abs(a - b) > 1e-8 for a, b in zip(
                        (fresh.MinimumDistance, fresh.MaximumDistance, fresh.Distance), bounds))):
                raise ValueError('New mate name or range did not match')
            doc.ClearSelection2(True)
            if not doc.ForceRebuild3(False) or feature.GetErrorCode2(False)[0] != 0:
                raise ValueError('Replacement mate rebuild failed')
            state.update(mate_name=mate_name, minimum_m=minimum_m,
                         maximum_m=maximum_m, distance_m=distance_m)
            return self._result(True, 'Limit mate recreated; changes are unsaved and feature identity changed', data=state)
        except Exception as exc:
            logging.getLogger(__name__).exception('Mate replacement failed; state=%s', state)
            state['partial_change'] = state['original_deleted']
            return self._result(False, str(exc), SwErrors.swFeatureError, data=state)
