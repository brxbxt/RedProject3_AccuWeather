import requests
import json
from flask import Flask, render_template, request, jsonify
import plotly.graph_objects as go
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
from datetime import datetime

API_KEY1 = "hipMbZ8XD03CZM2O9xCunVPnR0XmpUgW"
API_KEY2 = "RMErQKiIGTCT6RWuMV2W7sZ4g63c4sX4"
API_KEY = "LQAXuFiGjr6Lwtccrmb5zO7OxAl4DGFt"
LOCATIONS_FILE = "static/locations.json"

def load_locations():
    try:
        with open(LOCATIONS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_locations(locations):
    with open(LOCATIONS_FILE, "w", encoding="utf-8") as file:
        json.dump(locations, file, ensure_ascii=False, indent=4)

locations = load_locations()

# Функция для получения прогноза погоды на 5 дней
def get_weather_data(latitude, longitude):
    try:
        # Получение locationKey по координатам
        location_url = "http://dataservice.accuweather.com/locations/v1/cities/geoposition/search"
        location_params = {
            "apikey": API_KEY,
            "q": f"{latitude},{longitude}",
            "language": "ru-ru"
        }
        response = requests.get(location_url, params=location_params)
        response.raise_for_status()
        location_data = response.json()
        location_key = location_data["Key"]

        # Получение прогноза на 5 дней
        forecast_url = f"http://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}"
        forecast_params = {
            "apikey": API_KEY,
            "language": "ru-ru",
            "details": True,
            "metric": True
        }
        response = requests.get(forecast_url, params=forecast_params)
        response.raise_for_status()
        forecast_data = response.json()

        # Извлечение данных
        dates = []
        temperatures = []
        humidities = []
        wind_speeds = []
        precip_probs = []

        print(forecast_data["DailyForecasts"])

        for day in forecast_data["DailyForecasts"]:
            dates.append(datetime.fromtimestamp(day["EpochDate"]).strftime('%Y-%m-%d'))
            temperatures.append(round((day["Temperature"]["Minimum"]["Value"] + day["Temperature"]["Maximum"]["Value"]) / 2, 1))
            wind_speeds.append(day["Day"]["Wind"]["Speed"]["Value"])
            precip_probs.append(day["Day"]["PrecipitationProbability"])
            humidities.append(round((day["Day"]["RelativeHumidity"]["Minimum"] + day["Day"]["RelativeHumidity"]["Maximum"]) / 2))

        return {
            "Dates": dates,
            "Temperatures": temperatures,
            "Humidities": humidities,
            "Wind_speeds": wind_speeds,
            "Precip_probs": precip_probs
        }
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к API: {e}")
        return None
    except KeyError as e:
        print(f"Ошибка обработки данных JSON: {e}")
        return None

def check_bad_weather(temperature, wind_speed, precipitation_probability):
    str_to_return = "Good"
    if temperature < 0 or temperature > 35 or wind_speed > 50 or precipitation_probability > 70:
        str_to_return = "Bad"
        if temperature < 0:
            str_to_return += ", слишком холодно"
        if temperature > 35:
            str_to_return += ", слишком жарко"
        if wind_speed > 50:
            str_to_return += ", слишком сильный ветер"
        if precipitation_probability > 70:
            str_to_return += ", слишком высокая вероятность осадков"
    return str_to_return

def get_city_name_from_coordinates(latitude, longitude):
    url = "http://dataservice.accuweather.com/locations/v1/cities/geoposition/search"
    params = {
        "apikey": API_KEY,
        "q": f"{latitude},{longitude}",
        "language": "ru-ru"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        city_name = str(data['ParentCity']['LocalizedName']).lower().title()
        return city_name
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к API: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Ошибка обработки данных JSON: {e}")
        return None

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    weather_condition = None
    error_message = None
    overall_condition = None

    if request.method == 'POST':
        try:
            start_location = str(request.form['start_location']).lower().title()
            end_location = str(request.form['end_location']).lower().title()

            if start_location is None or end_location is None:
                raise ValueError("Не удалось получить координаты.")

            start_latitude, start_longitude = get_coordinates(start_location)
            end_latitude, end_longitude = get_coordinates(end_location)
            if start_latitude is None or start_longitude is None or end_latitude is None or end_longitude is None:
                raise ValueError("Не удалось получить координаты.")

            start_weather = get_weather_data(start_latitude, start_longitude)
            end_weather = get_weather_data(end_latitude, end_longitude)

            if start_weather is None:
                raise ValueError(
                    f"Ошибка получения данных о погоде для '{start_location}'. Возможно, проблема с API или сетью.")
            if end_weather is None:
                raise ValueError(
                    f"Ошибка получения данных о погоде для '{end_location}'. Возможно, проблема с API или сетью.")

            start_condition = check_bad_weather(start_weather['Temperatures'][0], start_weather['Wind_speeds'][0], start_weather['Precip_probs'][0])
            end_condition = check_bad_weather(end_weather['Temperatures'][0], end_weather['Wind_speeds'][0], end_weather['Precip_probs'][0])

            weather_condition = {
                "start": {"location": start_location, "condition": start_condition},
                "end": {"location": end_location, "condition": end_condition}
            }

            if start_condition != "Good" or end_condition != "Good":
                overall_condition = "Сейчас не время для путешествий!"
            else:
                overall_condition = "Можно отправляться!"

        except (KeyError, ValueError, requests.exceptions.RequestException) as e:
            error_message = f"Ошибка: {e}"

    return render_template('index.html', weather_condition=weather_condition, error_message=error_message, overall_condition=overall_condition)

@app.route('/add_city', methods=['GET', 'POST'])
def add_city():
    error_message = None
    success_message = None

    if request.method == 'POST':
        latitude = request.form['latitude']
        longitude = request.form['longitude']

        if latitude and longitude:
            try:
                latitude = float(latitude)
                longitude = float(longitude)

                city_name = str(get_city_name_from_coordinates(latitude, longitude)).lower().title()

                if city_name:
                    locations[city_name] = (latitude, longitude)
                    save_locations(locations)
                    success_message = f"Город {city_name} успешно добавлен!"
                else:
                    error_message = "Не удалось найти город по данным координатам."
            except ValueError:
                error_message = "Ошибка: координаты должны быть числовыми."
        else:
            error_message = "Ошибка: все поля должны быть заполнены."

    return render_template('add_city.html', locations=locations, error_message=error_message, success_message=success_message)

def get_coordinates(location_name):
    return locations.get(location_name)

# Dash-приложение для графиков
app_dash = dash.Dash(__name__, server=app, url_base_pathname='/dashboard/')
app_dash.layout = html.Div([
    html.H1("Прогноз погоды на 5 дней"),
    dcc.Dropdown(
        id='city-dropdown',
        options=[{'label': city, 'value': city} for city in locations.keys()],
        value=list(locations.keys())[0] if locations else None
    ),
    dcc.Graph(id='weather-graph'),
    dcc.RadioItems(
        id='parameter-selector',
        options=[
            {'label': 'Температура (°C)', 'value': 'Temperatures'},
            {'label': 'Влажность (%)', 'value': 'Humidities'},
            {'label': 'Скорость ветра (км/ч)', 'value': 'Wind_speeds'},
            {'label': 'Вероятность осадков (%)', 'value': 'Precip_probs'}
        ],
        value='Temperatures',
        inline=True
    ),
    dcc.RangeSlider(
        id='time-slider',
        min=0,
        max=4,
        step=1,
        marks={i: f"День {i + 1}" for i in range(5)},
        value=[0, 4]
    ),
    html.A(html.Button('Вернуться на главную'), href='/')
])


@app_dash.callback(
    Output('weather-graph', 'figure'),
    [Input('city-dropdown', 'value'),
     Input('parameter-selector', 'value'),
     Input('time-slider', 'value')]
)
def update_graph(selected_city, parameter, time_range):
    if not selected_city or not parameter:
        return go.Figure()

    latitude, longitude = locations[selected_city]
    forecast_data = get_weather_data(latitude, longitude)
    if not forecast_data:
        return go.Figure()

    # Применение временного интервала
    start, end = time_range
    x_data = forecast_data["Dates"][start:end + 1]
    y_data = forecast_data[parameter][start:end + 1]

    return go.Figure(
        data=[go.Scatter(x=x_data, y=y_data, mode='lines+markers', name=parameter)],
        layout=go.Layout(title=f"{parameter} в городе {selected_city} (5 дней)", xaxis_title="Дата", yaxis_title=parameter)
    )

if __name__ == '__main__':
    app.run(debug=True)