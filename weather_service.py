"""
天气信息获取服务
默认使用 Open-Meteo（免费、无需 API Key），可选和风天气 / OpenWeatherMap
"""
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
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

    def fetch(self, city: str) -> Optional[WeatherInfo]:
        """获取天气信息，子类实现"""
        raise NotImplementedError


class OpenMeteoProvider(WeatherProvider):
    """
    Open-Meteo 天气 API 提供者
    完全免费，无需 API Key，适合个人项目
    文档: https://open-meteo.com/
    """
    GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

    # WMO 天气代码映射
    CONDITION_MAP = {
        0: "晴",
        1: "主要晴朗",
        2: "部分多云",
        3: "多云",
        4: "阴天",
        5: "薄雾",
        6: "霾",
        7: "浮尘",
        8: "烟",
        9: "浮尘",
        10: "轻雾",
        45: "雾",
        48: "雾凇",
        51: "毛毛雨",
        53: "毛毛雨",
        55: "毛毛雨",
        56: "冻毛毛雨",
        57: "冻毛毛雨",
        61: "小雨",
        63: "中雨",
        65: "大雨",
        66: "冻雨",
        67: "冻雨",
        71: "小雪",
        73: "中雪",
        75: "大雪",
        77: "雪粒",
        80: "阵雨",
        81: "中阵雨",
        82: "大阵雨",
        85: "阵雪",
        86: "阵雪",
        95: "雷雨",
        96: "雷阵雨",
        99: "强雷阵雨",
    }

    def fetch(self, city: str) -> Optional[WeatherInfo]:
        try:
            # 1. 地理编码：城市名 -> 经纬度
            geo_url = f"{self.GEO_URL}?name={urllib.parse.quote(city)}&count=1&language=zh&format=json"
            req = urllib.request.Request(geo_url, headers={"User-Agent": "DesktopPet/2.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                geo_data = json.loads(resp.read().decode("utf-8"))

            results = geo_data.get("results", [])
            if not results:
                logger.warning(f"Open-Meteo 未找到城市: {city}")
                return None

            lat = results[0]["latitude"]
            lon = results[0]["longitude"]
            city_name = results[0].get("name", city)

            # 2. 获取实时天气
            weather_url = (
                f"{self.WEATHER_URL}?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,weather_code"
                f"&timezone=auto"
            )
            req = urllib.request.Request(weather_url, headers={"User-Agent": "DesktopPet/2.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                weather_data = json.loads(resp.read().decode("utf-8"))

            current = weather_data.get("current", {})
            wmo_code = current.get("weather_code", 0)

            return WeatherInfo(
                city=city_name,
                temperature=current.get("temperature_2m", 0),
                condition=self.CONDITION_MAP.get(wmo_code, "未知"),
                humidity=current.get("relative_humidity_2m"),
                update_time=datetime.now().strftime("%H:%M"),
            )

        except Exception as e:
            logger.error(f"Open-Meteo 查询异常: {e}")
            return None


class QWeatherProvider(WeatherProvider):
    """和风天气 API 提供者"""
    GEO_URL = "https://geoapi.qweather.com/v2/city/lookup"
    WEATHER_URL = "https://devapi.qweather.com/v7/weather/now"

    def fetch(self, city: str, api_key: str = "") -> Optional[WeatherInfo]:
        if not api_key:
            return None

        try:
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

    def fetch(self, city: str, api_key: str = "") -> Optional[WeatherInfo]:
        if not api_key:
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
        self._provider_name = self._config.get("api_provider", "openmeteo")
        self._last_result: Optional[WeatherInfo] = None
        self._last_fetch_time: Optional[datetime] = None

        self._providers: List[WeatherProvider] = []
        self._init_providers()

    def _init_providers(self):
        """按优先级初始化提供者"""
        providers = []

        # 根据配置添加对应提供者
        if self._provider_name == "qweather":
            providers.append(QWeatherProvider())
        elif self._provider_name == "openweathermap":
            providers.append(OpenWeatherProvider())

        # Open-Meteo 始终作为兜底（无需 API Key）
        providers.append(OpenMeteoProvider())

        self._providers = providers

    def get_weather(self, city: str) -> Optional[WeatherInfo]:
        """
        获取天气信息
        策略: 依次尝试各提供者，返回第一个成功结果
        Open-Meteo 无需 Key 可直接使用
        """
        logger.info(f"查询天气: {city} (provider: {self._provider_name})")

        for provider in self._providers:
            try:
                # Open-Meteo 不需要 api_key，其他需要
                if isinstance(provider, OpenMeteoProvider):
                    info = provider.fetch(city)
                else:
                    info = provider.fetch(city, self._api_key)

                if info is not None:
                    self._last_result = info
                    self._last_fetch_time = datetime.now()
                    logger.info(f"天气查询成功: {info.city} {info.condition} {info.temperature}°C")
                    return info
            except Exception as e:
                logger.debug(f"提供者 {type(provider).__name__} 失败: {e}")
                continue

        logger.warning(f"所有天气API均不可用")
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
