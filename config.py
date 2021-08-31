import os

FLASK_DEBUG = False
PYCHARM_DEBUG= False
# Create dummy secrey key so we can use sessions
SECRET_KEY = '123456790'
SECRET_KEY_FILE = 'secret_key'

#BASE_PATH = os.path.dirname(os.path.abspath(__file__))
#TEMPLATE_PATH = os.path.join(BASE_PATH, 'app/vue_frontend/dist')
#STATIC_PATH = os.path.join(BASE_PATH, 'app/vue_frontend/dist')

# Create in-memory database
DATABASE_FILE = 'wq_db.sqlite'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE_FILE
SQLALCHEMY_ECHO = False

IS_MAINTENANCE_MODE = False

if PYCHARM_DEBUG:
  LOGFILE='/Users/danramage/tmp/log/flask_plug_view_site.log'
else:
  LOGFILE='/var/log/wq_rest/devapiflaskvuesite.log'

VALID_UPDATE_ADDRESSES = ['127.0.0.1', '129.252.139.113', '129.252.139.170']
CURRENT_SITE_LIST = ['myrtlebeach', 'sarasota', 'charleston', 'killdevilhill']

if not PYCHARM_DEBUG:
  SITES_CONFIG = {
    'myrtlebeach':
      {
        'prediction_file': '/home/xeniaprod/feeds/sc_wq/vb_engine/Predictions.json',
        'advisory_file': '/home/xeniaprod/feeds/sc_wq/vb_engine/monitorstations/beachAdvisoryResults.json',
        'stations_directory': '/home/xeniaprod/feeds/sc_wq/vb_engine/monitorstations'
      },
    'surfside':
      {
        'prediction_file': '/home/xeniaprod/feeds/sc_wq/vb_engine/Predictions.json',
        'advisory_file': '/home/xeniaprod/feeds/sc_wq/vb_engine/monitorstations/beachAdvisoryResults.json',
        'stations_directory': '/home/xeniaprod/feeds/sc_wq/vb_engine/monitorstations'
      },
    'sarasota':
      {
        'prediction_file': '/home/xeniaprod/feeds/fl_wq/Predictions.json',
        'advisory_file': '/home/xeniaprod/feeds/fl_wq/monitorstations/beachAdvisoryResults.json',
        'stations_directory': '/home/xeniaprod/feeds/fl_wq/monitorstations',
        'ripcurrents': '/home/xeniaprod/feeds/fl_wq/nwsforecasts/forecasts.json'
  },
    'charleston':
      {
        'prediction_file': '/home/xeniaprod/feeds/charleston/Predictions.json',
        'advisory_file': '/home/xeniaprod/feeds/charleston/monitorstations/beach_advisories.json',
        'stations_directory': '/home/xeniaprod/feeds/charleston/monitorstations'
      },
      'killdevilhills':
      {
        'prediction_file': '/home/xeniaprod/feeds/northcarolina/killdevilhills/Predictions.json',
        'advisory_file': '/home/xeniaprod/feeds/northcarolina/killdevilhills/monitorstations/kdh_beach_advisories.json',
        'stations_directory': '/home/xeniaprod/feeds/northcarolina/killdevilhills/monitorstations'
      },
    'follybeach':
      {
        'prediction_file': '/home/xeniaprod/feeds/follybeach/Predictions.json',
        'advisory_file': '/home/xeniaprod/feeds/follybeach/monitorstations/beach_advisories.json',
        'stations_directory': '/home/xeniaprod/feeds/follybeach/monitorstations',
        'camera_statistics': '',
        'shellfish_closures': '/home/xeniaprod/feeds/follybeach/shellfish/shellfish_closures.json',
        'ripcurrents': '/home/xeniaprod/feeds/follybeach/ripcurrent/forecasts.json',
        'camera_rest':  {
          'url': 'https://www.floridaapdata.org/beach/response_beach.php'
        }
      },
  }
else:
  SITES_CONFIG = {
    'myrtlebeach':
      {
        'prediction_file': '/Users/danramage/tmp/wq_feeds/sc_mb/Predictions.json',
        'advisory_file': '/Users/danramage/tmp/wq_feeds/sc_mb/monitorstations/beachAdvisoryResults.json',
        'stations_directory': '/Users/danramage/tmp/wq_feeds/sc_mb/monitorstations'
      },
    'surfside':
      {
        'prediction_file': '/Users/danramage/tmp/wq_feeds/sc_mb/Predictions.json',
        'advisory_file': '/Users/danramage/tmp/wq_feeds/sc_mb/monitorstations/beachAdvisoryResults.json',
        'stations_directory': '/Users/danramage/tmp/wq_feeds/sc_mb/monitorstations'
      },
    'charleston':
      {
        'prediction_file': '/Users/danramage/tmp/wq_feeds/charleston/Predictions.json',
        'advisory_file': '/Users/danramage/tmp/wq_feeds/charleston/monitorstations/beach_advisories.json',
        'stations_directory': '/Users/danramage/tmp/wq_feeds/charleston/monitorstations'
      },
      'killdevilhills':
      {
        'prediction_file': '/Users/danramage/tmp/wq_feeds/kdh/Predictions.json',
        'advisory_file': '/Users/danramage/tmp/wq_feeds/kdh/monitorstations/kdh_beach_advisories.json',
        'stations_directory': '/Users/danramage/tmp/wq_feeds/kdh/monitorstations'
      },
    'follybeach':
      {
        'prediction_file': '/Users/danramage/Documents/workspace/WaterQuality/FollyBeach-WaterQuality/data/test_outputs/Predictions.json',
        'advisory_file': '/Users/danramage/Documents/workspace/WaterQuality/FollyBeach-WaterQuality/data/test_outputs/beach_advisories.json',
        'stations_directory': '/Users/danramage/Documents/workspace/WaterQuality/FollyBeach-WaterQuality/data/test_outputs/',
        'camera_statistics': '/Users/danramage/Documents/workspace/WaterQuality/FollyBeach-WaterQuality/data/camera/summary_data.json',
        'shellfish_closures': '/Users/danramage/Documents/workspace/WaterQuality/FollyBeach-WaterQuality/data/shellfish/shellfish_closures.json',
        'ripcurrents': '/Users/danramage/tmp/wq_feeds/sc_folly_beach/forecasts.json'
      },
    'sarasota':
      {
        'prediction_file': '/Users/danramage/tmp/wq_feeds/fl_wq/Predictions.json',
        'advisory_file': '/Users/danramage/tmp/wq_feeds/fl_wq/monitorstations/beachAdvisoryResults.json',
        'stations_directory': '/Users/danramage/tmp/wq_feeds/feeds/fl_wq/monitorstations',
        'ripcurrents': '/Users/danramage/tmp/wq_feeds/sarasota/forecasts.json'
  },

  }

#Number of hours the advisory should be considered valid.
SITE_TYPE_DATA_VALID_TIMEOUTS= {
  'Default': 192,
  'Nowcast': 24,
  'Shellfish': 24,
  'Rip Current': 4
}