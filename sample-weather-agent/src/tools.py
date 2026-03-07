"""
Tools for the weather assistant agent.
Define your LangChain tools here.
"""
import json
import requests
from typing import List, Dict, Any
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """
    Get current weather information for a city.
    
    Args:
        city: Name of the city to get weather for
    """
    try:
        # Using a free weather API (OpenWeatherMap requires API key in production)
        # For demo purposes, we'll simulate weather data
        simulated_weather = {
            "london": {"temp": "15°C", "condition": "Cloudy", "humidity": "75%"},
            "new york": {"temp": "22°C", "condition": "Sunny", "humidity": "60%"},
            "tokyo": {"temp": "18°C", "condition": "Rainy", "humidity": "85%"},
            "paris": {"temp": "12°C", "condition": "Partly Cloudy", "humidity": "70%"},
            "mumbai": {"temp": "28°C", "condition": "Hot", "humidity": "80%"}
        }
        
        city_lower = city.lower()
        if city_lower in simulated_weather:
            weather = simulated_weather[city_lower]
            return f"Weather in {city.title()}: {weather['temp']}, {weather['condition']}, Humidity: {weather['humidity']}"
        else:
            return f"Weather data not available for {city}. Available cities: London, New York, Tokyo, Paris, Mumbai"
            
    except Exception as e:
        return f"Error retrieving weather data: {str(e)}"

@tool
def get_weather_forecast(city: str, days: int = 3) -> str:
    """
    Get weather forecast for a city.
    
    Args:
        city: Name of the city to get forecast for
        days: Number of days to forecast (default: 3)
    """
    try:
        if days > 7:
            days = 7
        if days < 1:
            days = 1
            
        # Simulated forecast data
        forecast_data = {
            "london": ["Cloudy, 15°C", "Rainy, 12°C", "Sunny, 18°C", "Cloudy, 14°C", "Partly Cloudy, 16°C"],
            "new york": ["Sunny, 22°C", "Partly Cloudy, 20°C", "Sunny, 25°C", "Thunderstorms, 19°C", "Sunny, 23°C"],
            "tokyo": ["Rainy, 18°C", "Cloudy, 16°C", "Sunny, 21°C", "Partly Cloudy, 19°C", "Rainy, 17°C"]
        }
        
        city_lower = city.lower()
        if city_lower in forecast_data:
            forecast = forecast_data[city_lower][:days]
            result = f"{days}-day forecast for {city.title()}:\n"
            for i, day_weather in enumerate(forecast, 1):
                result += f"Day {i}: {day_weather}\n"
            return result.strip()
        else:
            return f"Forecast data not available for {city}. Available cities: London, New York, Tokyo"
            
    except Exception as e:
        return f"Error retrieving forecast data: {str(e)}"

@tool
def convert_temperature(temperature: float, from_unit: str, to_unit: str) -> str:
    """
    Convert temperature between different units.
    
    Args:
        temperature: Temperature value to convert
        from_unit: Source unit (C, F, K)
        to_unit: Target unit (C, F, K)
    """
    try:
        from_unit = from_unit.upper()
        to_unit = to_unit.upper()
        
        # Convert to Celsius first
        if from_unit == 'F':
            celsius = (temperature - 32) * 5/9
        elif from_unit == 'K':
            celsius = temperature - 273.15
        elif from_unit == 'C':
            celsius = temperature
        else:
            return f"Invalid source unit: {from_unit}. Use C, F, or K."
        
        # Convert from Celsius to target unit
        if to_unit == 'F':
            result = (celsius * 9/5) + 32
        elif to_unit == 'K':
            result = celsius + 273.15
        elif to_unit == 'C':
            result = celsius
        else:
            return f"Invalid target unit: {to_unit}. Use C, F, or K."
        
        return f"{temperature}°{from_unit} = {result:.1f}°{to_unit}"
        
    except Exception as e:
        return f"Error converting temperature: {str(e)}"
