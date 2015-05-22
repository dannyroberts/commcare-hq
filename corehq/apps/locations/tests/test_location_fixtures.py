from django.test import SimpleTestCase
from corehq.apps.locations.models import SQLLocation, LocationType
from ..fixtures import _location_to_fixture, _location_footprint


class LocationFixturesTest(SimpleTestCase):

    def test_metadata(self):
        state = LocationType(
            domain="test-domain",
            name="state",
            code="state",
        )

        location = SQLLocation(
            location_id="unique-id",
            domain="test-domain",
            name="Braavos",
            location_type=state,
            metadata={'best_swordsman': "Sylvio Forel",
                      'in_westeros': "false"},
        )
        location_db = _location_footprint([location])
        fixture = _location_to_fixture(location_db, location)
        location_data = {
            e.tag: e.text for e in fixture.find('location_data')
        }
        self.assertEquals(location_data, location.metadata)
