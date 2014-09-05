from annoying.functions import get_object_or_None
from tastypie.exceptions import NotFound, BadRequest
from tastypie.resources import Resource, ModelResource

from kalite.facility.models import Facility, FacilityGroup, FacilityUser
from kalite.main.models import AttemptLog
from kalite.shared.api_auth import ObjectAdminAuthorization
from kalite.student_testing.models import TestLog
from securesync.models import Zone

from .api_serializers import CSVSerializer


class FacilityResource(ModelResource):
    class Meta:
        queryset = Facility.objects.all()
        resource_name = 'facility'
        authorization = ObjectAdminAuthorization()

    def obj_get_list(self, bundle, **kwargs):
        # Allow filtering facilities by zone
        zone_id = bundle.request.GET.get('zone_id')
        if zone_id:
            facility_list = Facility.objects.by_zone(get_object_or_None(Zone, id=zone_id))
        else:
            facility_list = Facility.objects.all()

        # call super to trigger auth
        return super(FacilityResource, self).authorized_read_list(facility_list, bundle)
        

class FacilityGroupResource(ModelResource):
    class Meta:
        queryset = FacilityGroup.objects.all()
        resource_name = 'group'
        authorization = ObjectAdminAuthorization()

    def obj_get_list(self, bundle, **kwargs):
        # Allow filtering groups by facility
        facility_id = bundle.request.GET.get('facility_id')
        if facility_id:
            group_list = FacilityGroup.objects.filter(facility__id=facility_id)
        else:
            group_list = FacilityGroup.objects.all()

        # call super to trigger auth
        return super(FacilityGroupResource, self).authorized_read_list(group_list, bundle)


class ParentFacilityUserResource(ModelResource):
    """A class with helper methods for getting facility users for data export requests"""

    def _get_facility_users(self, bundle):
        """Return a list of facility users and their ids specified by the zone id(s), facility_id, or group_id"""
        zone_id = bundle.request.GET.get('zone_id')
        zone_ids = bundle.request.GET.get('zone_ids')
        facility_id = bundle.request.GET.get('facility_id')
        group_id = bundle.request.GET.get('group_id')

        # They must have a zone_id, and may have a facility_id and group_id.
        # Try to filter from most specific, to least 
        facility_user_objects = []
        if group_id:
            facility_user_objects = FacilityUser.objects.filter(group__id=group_id)
        elif facility_id:
            facility_user_objects = FacilityUser.objects.filter(facility__id=facility_id)
        elif zone_id:
            facility_user_objects = FacilityUser.objects.by_zone(get_object_or_None(Zone, id=zone_id))
        elif zone_ids:
            # Assume 'all' selected for zone, and a list of zone ids has been passed
            zone_ids = zone_ids.split(",")
            facility_user_objects = []
            for zone_id in zone_ids:
                facility_user_objects += FacilityUser.objects.by_zone(get_object_or_None(Zone, id=zone_id))
        # TODO(dylanjbarth) errors commented out so we can pass a blank CSV if not found.
        # in future, should handle these more gracefully, with a redirect, an AJAX warning,
        # and reset the fields. see: https://gist.github.com/1116962/58b7db0364de837ce229cdd8ef524bc9ff6da19f
        # else:
        #     raise BadRequest("Invalid request.")

        # if not facility_user_objects:
        #     raise NotFound("Student not found.")

        facility_user_ids = [facility_user.id for facility_user in facility_user_objects]
        return facility_user_ids, facility_user_objects


class FacilityUserResource(ParentFacilityUserResource):

    class Meta:
        queryset = FacilityUser.objects.all()
        resource_name = 'facility_user_csv'
        authorization = ObjectAdminAuthorization()
        excludes = ['password', 'signature', 'deleted', 'signed_version', 'counter', 'notes']
        serializer = CSVSerializer()

    def obj_get_list(self, bundle, **kwargs):
        facility_user_ids, facility_user_objects = self._get_facility_users(bundle)
        return super(FacilityUserResource, self).authorized_read_list(facility_user_objects, bundle)

    def alter_list_data_to_serialize(self, request, to_be_serialized):
        for bundle in to_be_serialized["objects"]:
            user_facility = FacilityUser.objects.get(id=bundle.data["id"]).facility
            bundle.data["facility_name"] = user_facility.name
            bundle.data["facility_id"] = user_facility.id

        return to_be_serialized


class TestLogResource(ParentFacilityUserResource):

    class Meta:
        queryset = TestLog.objects.all()
        resource_name = 'test_log_csv'
        authorization = ObjectAdminAuthorization()
        excludes = ['counter', 'signature', 'deleted', 'signed_version', 'index']
        serializer = CSVSerializer()

    def obj_get_list(self, bundle, **kwargs):
        facility_user_ids, facility_user_objects = self._get_facility_users(bundle)
        test_logs = TestLog.objects.filter(user__id__in=facility_user_ids)
        # if not test_logs:
        #     raise NotFound("No test logs found.")
        return super(TestLogResource, self).authorized_read_list(test_logs, bundle)


class AttemptLogResource(ParentFacilityUserResource):

    class Meta:
        queryset = AttemptLog.objects.all()
        resource_name = 'attempt_log_csv'
        authorization = ObjectAdminAuthorization()
        excludes = ['signed_version', 'language', 'deleted', 'response_log', 'answer_given', 'signature', 'version', 'timestamp']
        serializer = CSVSerializer()

    def obj_get_list(self, bundle, **kwargs):
        facility_user_ids, facility_user_objects = self._get_facility_users(bundle)
        attempt_logs = AttemptLog.objects.filter(user__id__in=facility_user_ids)
        # if not attempt_logs:
        #     raise NotFound("No attempt logs found.")
        return super(AttemptLogResource, self).authorized_read_list(attempt_logs, bundle)


