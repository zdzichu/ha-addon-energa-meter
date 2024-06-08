from peewee import SqliteDatabase, PostgresqlDatabase
from flask import Flask, jsonify, request, redirect, url_for, abort
from waitress import serve
#from datetime 
import datetime
import time, os, logging
from moj_licznik import PPETable, MeterTable, CounterTable, MainChartTable
import urllib.parse

logger = logging.getLogger("energaMeter.api")

if postgresql_connstring := os.getenv("POSTGRESQL_CONNSTRING"):
    from psycopg2.extensions import parse_dsn
    db_name = parse_dsn(postgresql_connstring)['dbname']
    db = PostgresqlDatabase(db_name, dsn=postgresql_connstring)
else:
    path = os.path.dirname(os.path.abspath(__file__))
    db_file = 'data/database.sqlite'
    db = SqliteDatabase(os.path.join(path, db_file))

app = Flask(__name__)

@app.route('/', methods=['GET'])
def root():
    query = PPETable.select() #.where(PPETable.is_active == True)
    result_ppes = list(query)
    ppes = []
    for p in result_ppes:
        meters_query = MeterTable.select().where(MeterTable.ppe_id == p.id)
        meter_result = meters_query.execute()
        meters = []
        for meter in meter_result:
            countners_query = CounterTable.select().where(CounterTable.meter_id == meter.id)
            countners_result = countners_query.execute()
            countners = []
            for countner in countners_result:
                countner = {
                    'tariff': countner.tariff,
                    'measurement_date': countner.measurement_date,
                    'meter_value': countner.meter_value
                }
                countners.append(countner)

            meter = {
                'meter_type': meter.meter_type,
                'meter_type_url': urllib.parse.quote_plus(meter.meter_type),
                'last_update_date': meter.last_update_date,
                'first_date': meter.first_date,
                'countners': countners
            }
            meters.append(meter)

        ppe = {
            'name': p.name,
            'id': p.id,
            'type': p.type,
            'isActive': p.is_active,
            'meters': meters
        }
        ppes.append(ppe)
    logger.debug("API: GET /")
    
    return jsonify({'ppes': ppes})

@app.route('/meters', methods=['GET'])
@app.route('/meters/', methods=['GET'])
def meters():
    query = PPETable.select() #.where(PPETable.is_active == True)
    result_ppes = list(query)
    meters = []

    for p in result_ppes:
        meter = {
            'name': p.name,
            'id': p.id,
            'ppe': p.ppe,
            'number_of_zones': '',#p.number_of_zones,
            'tariffCode': p.tariffCode,
            # 'first_date': p.first_date,
            'last_update_date': p.last_update_date,
            # 'measurement_date': p.measurement_date,
        }

        for i in range(1, p.number_of_zones + 1):
            zone_key = f'zone{i}'
            daily_chart_key = f'zone{i}_daily_chart_sum'

            zone_value = getattr(p, zone_key)
            daily_chart_value = getattr(p, daily_chart_key)

            # Zamień None na zero podczas obliczania sumy
            zone_value = float(zone_value) if zone_value is not None else 0
            daily_chart_value = float(daily_chart_value) if daily_chart_value is not None else 0

            meter[zone_key] = {
                'meter': zone_value,
                'daily_chart': daily_chart_value,
                'sum': zone_value + daily_chart_value
            }

        meters.append(meter)
    logger.debug("GET /meters")
    
    return jsonify({'meters': meters})


@app.route('/<int:ppe_id>', methods=['GET'])
@app.route('/<int:ppe_id>/', methods=['GET'])
def get_ppe(ppe_id):
        meters_query = MeterTable.select().where(MeterTable.ppe_id == ppe_id)
        meter_result = meters_query.execute()

        if not meter_result:
            abort(404)
        
        meters = []
        for meter in meter_result:
            countners_query = CounterTable.select().where(CounterTable.meter_id == meter.id)
            countners_result = countners_query.execute()
            countners = []
            for countner in countners_result:
                countner = {
                    'tariff': countner.tariff,
                    'measurement_date': countner.measurement_date,
                    'meter_value': countner.meter_value
                }
                countners.append(countner)

            meter = {
                'meter_type': meter.meter_type,
                'meter_type_url': urllib.parse.quote_plus(meter.meter_type),
                'last_update_date': meter.last_update_date,
                'first_date': meter.first_date,
                'countners': countners
            }
            meters.append(meter)
        logger.debug(f"API: GET /{ppe_id}")
        return jsonify({'meters': meters})


@app.route('/<int:ppe_id>/<meter_type_url>', methods=['GET'])
@app.route('/<int:ppe_id>/<meter_type_url>/', methods=['GET'])
def get_meter_type(ppe_id, meter_type_url):
        meter_type = urllib.parse.unquote(meter_type_url)
        meters_query = MeterTable.select().where((MeterTable.ppe_id == str(ppe_id)) & (MeterTable.meter_type == meter_type))
        meter_result = meters_query.execute()
        if not meter_result:
             abort(404)

        meter = meter_result[0]
        countners_query = CounterTable.select().where(CounterTable.meter_id == meter.id)
        countners_result = countners_query.execute()
        countners = []
        for countner in countners_result:
            countner = {
                'tariff': countner.tariff,
                'measurement_date': countner.measurement_date,
                'meter_value': countner.meter_value
            }
            countners.append(countner)

        meter = {
            'meter_type': meter.meter_type,
            'meter_type_url': urllib.parse.quote_plus(meter.meter_type),
            'last_update_date': meter.last_update_date,
            'first_date': meter.first_date,
            'countners': countners
        }

        logger.debug(f"API: GET /{ppe_id}/{meter_type_url}")
        return jsonify({'meter': meter})

@app.route('/<int:ppe_id>/<meter_type_url>/<tariff>', methods=['GET'])
@app.route('/<int:ppe_id>/<meter_type_url>/<tariff>/', methods=['GET'])
def get_countners(ppe_id, meter_type_url, tariff):
        meter_type = urllib.parse.unquote(meter_type_url)
        meters_query = MeterTable.select().where((MeterTable.ppe_id == str(ppe_id)) & (MeterTable.meter_type == meter_type))
        meter_result = meters_query.execute()

        if not meter_result:
            abort(404)

        meter = meter_result[0]
        countners_query = CounterTable.select().where((CounterTable.meter_id == meter.id) & (CounterTable.tariff == tariff))
        countners_result = countners_query.execute()
        countner = countners_result[0]
        countner = {
            'tariff': countner.tariff,
            'measurement_date': countner.measurement_date,
            'meter_value': countner.meter_value
        }

        logger.debug(f"API: GET /{ppe_id}/{meter_type_url}/{countner}")
        return jsonify({'countner': countner})



@app.route('/charts', methods=['GET'])
@app.route('/charts/', methods=['GET'])
def charts():
    

    current_time = datetime.datetime.now()
    current_time_unix = time.mktime(current_time.timetuple())
    start_time = current_time - datetime.timedelta(days=1)
    start_time_unix = time.mktime(start_time.timetuple())
    start_date = request.args.get('start_date', start_time_unix*1000)
    end_date = request.args.get('end_date', current_time_unix*1000)
    mp = request.args.get('mp', None)
    meter_type_url = request.args.get('meter_type_url', None)
    zone = request.args.get('zone', None)
    negative = request.args.get('negative', type=bool, default=False) 
    logger.debug(f"API: GET /charts - {start_date} - {end_date}")
    query = MainChartTable.select().where((MainChartTable.tm >= int(start_date)/1000) & (MainChartTable.tm <= int(end_date)/1000))
    logger.debug(f"{query}")
    factor = 1
    if negative:
         factor = -1
    if mp:
        query = query.where(MainChartTable.mp == mp)

    if meter_type_url:
        meter_type = urllib.parse.unquote(meter_type_url)
        query = query.where(MainChartTable.meter_type == meter_type)

    if zone:
        query = query.where(MainChartTable.zone == zone)

    result_ppes = list(query)
    charts = []

    for p in result_ppes:
        czas = p.tm.strftime("%Y-%m-%d %H:%M:%S")
        chart = {
            'mp': p.mp,
            'meter_type': p.meter_type,
            'meter_type_url': urllib.parse.quote_plus(p.meter_type),
            'zone': p.zone,
            'time_tm': int(p.tm.timestamp()*1000),
            'time': czas,
            'value': p.value * factor
        }
        charts.append(chart)
    end_time = time.time()

    return jsonify({'charts': charts})
