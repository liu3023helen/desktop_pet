"""
天气信息获取服务
支持多API提供商：和风天气、OpenWeatherMap
"""
import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("DesktopPet")


@dataclass
class WeatherInfo:
    """天气信息数据类"""
    city: str
    temperature: float          # 摄氏度
    condition: str              # 天气状况: 晴/多云/阴/雨/雪等
    humidity: Optional[int] = None   # 湿度百分比
    update_time: Optional[str] = None  # 更新时间


class WeatherProvider:
    """天气API提供者基类"""

    def fetch(self, city: str, api_key: str) -> Optional[WeatherInfo]:
        """获取天气信息，子类实现"""
        raise NotImplementedError


class QWeatherProvider(WeatherProvider):
    """和风天气 API 提供者"""
    # 免费版: 每小时300次调用，无需API Key即可使用基础天气（但建议申请Key）
    GEO_URL = "https://geoapi.qweather.com/v2/city/lookup"
    WEATHER_URL = "https://devapi.qweather.com/v7/weather/now"

    def fetch(self, city: str, api_key: str) -> Optional[WeatherInfo]:
        if not api_key:
            logger.warning("和风天气API Key未配置")
            return None

        try:
            # 1. 地理编码：城市名 -> location_id
            geo_url = f"{self.GEO_URL}?location={city}&key={api_key}&lang=zh"
            with urllib.request.urlopen(geo_url, timeout=8) as resp:
                geo_data = json.loads(resp.read().decode("utf-8"))

            if geo_data.get("code") != "200":
                logger.warning(f"和风天气城市查询失败: {geo_data.get('msg')}")
                return None

            locations = geo_data.get("location", [])
            if not locations:
                logger.warning(f"未找到城市: {city}")
                return None

            location_id = locations[0]["id"]
            city_name = locations[0]["name"]

            # 2. 获取实时天气
            weather_url = f"{self.WEATHER_URL}?location={location_id}&key={api_key}"
            with urllib.request.urlopen(weather_url, timeout=8) as resp:
                weather_data = json.loads(resp.read().decode("utf-8"))

            if weather_data.get("code") != "200":
                logger.warning(f"和风天气数据获取失败: {weather_data.get('msg')}")
                return None

            now = weather_data.get("now", {})
            return WeatherInfo(
                city=city_name,
                temperature=float(now.get("temp", 0)),
                condition=now.get("text", "未知"),
                humidity=int(now.get("humidity", 0)) if now.get("humidity") else None,
                update_time=datetime.now().strftime("%H:%M"),
            )

        except Exception as e:
            logger.error(f"和风天气查询异常: {e}")
            return None


class OpenWeatherProvider(WeatherProvider):
    """OpenWeatherMap API 提供者"""
    URL = "https://api.openweathermap.org/data/2.5/weather"

    def fetch(self, city: str, api_key: str) -> Optional[WeatherInfo]:
        if not api_key:
            logger.warning("OpenWeatherMap API Key未配置")
            return None

        try:
            url = (
                f"{self.URL}?q={city}&appid={api_key}"
                f"&units=metric&lang=zh_cn"
            )
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            return WeatherInfo(
                city=data.get("name", city),
                temperature=round(data["main"]["temp"], 1),
                condition=data["weather"][0]["description"] if data.get("weather") else "未知",
                humidity=data["main"].get("humidity"),
                update_time=datetime.now().strftime("%H:%M"),
            )

        except Exception as e:
            logger.error(f"OpenWeatherMap查询异常: {e}")
            return None


class WeatherService:
    """天气服务 - 自动选择可用的API提供者"""

    def __init__(self, config: Dict = None):
        self._config = config or {}
        self._api_key = self._config.get("api_key", "")
        self._provider_name = self._config.get("api_provider", "qweather")
        self._last_result: Optional[WeatherInfo] = None
        self._last_fetch_time: Optional[datetime] = None

        # 初始化提供者
        self._providers: List[WeatherProvider] = []
        self._init_providers()

    def _init_providers(self):
        """按优先级初始化提供者"""
        # 优先使用配置的提供者
        if self._provider_name == "openweathermap":
            self._providers = [OpenWeatherProvider(), QWeatherProvider()]
        else:
            self._providers = [QWeatherProvider(), OpenWeatherProvider()]

    def get_weather(self, city: str) -> Optional[WeatherInfo]:
        """
        获取天气信息
        策略: 依次尝试各提供者，返回第一个成功结果
        """
        logger.info(f"查询天气: {city}")

        for provider in self._providers:
            info = provider.fetch(city, self._api_key)
            if info is not None:
                self._last_result = info
                self._last_fetch_time = datetime.now()
                logger.info(f"天气查询成功: {info.city} {info.condition} {info.temperature}°C")
                return info

        # 所有提供者都失败
        logger.warning(f"所有天气API均不可用，返回上次缓存结果")
        return self._last_result

    def get_last_result(self) -> Optional[WeatherInfo]:
        """获取上次成功查询的天气信息"""
        return self._last_result

    def needs_refresh(self, interval_minutes: int = 60) -> bool:
        """检查是否需要刷新天气数据"""
        if self._last_fetch_time is None:
            return True
        age = (datetime.now() - self._last_fetch_time).total_seconds() / 60
        return age > interval_minutes
