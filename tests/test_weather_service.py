import unittest
from unittest.mock import Mock

from weather_service import WeatherInfo, WeatherService


class WeatherCacheTests(unittest.TestCase):
    def setUp(self):
        self.service = WeatherService({"update_interval_minutes": 60})
        self.provider = Mock()
        self.provider.fetch.return_value = WeatherInfo(
            city="北京", temperature=25.0, condition="晴", humidity=0
        )
        self.service._providers = [self.provider]

    def test_same_city_uses_cache_until_forced(self):
        first = self.service.get_weather("北京")
        second = self.service.get_weather("北京")
        forced = self.service.get_weather("北京", force=True)

        self.assertIs(first, second)
        self.assertIs(forced, first)
        self.assertEqual(self.provider.fetch.call_count, 2)

    def test_failed_different_city_does_not_return_wrong_cache(self):
        self.service.get_weather("北京")
        self.provider.fetch.return_value = None

        result = self.service.get_weather("上海")

        self.assertIsNone(result)

    def test_empty_city_is_rejected_without_provider_call(self):
        result = self.service.get_weather("  ")

        self.assertIsNone(result)
        self.provider.fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
