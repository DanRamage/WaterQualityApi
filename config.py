import os

FLASK_DEBUG = True
PYCHARM_DEBUG= True
# Create dummy secrey key so we can use sessions
SECRET_KEY = '123456790'
SECRET_KEY_FILE = 'secret_key'

# Create in-memory database
DATABASE_FILE = 'wq_db.sqlite'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE_FILE
SQLALCHEMY_ECHO = False

IS_MAINTENANCE_MODE = False

if PYCHARM_DEBUG:
  LOGFILE='/Users/danramage/tmp/log/flask_plug_view_site.log'
  DATA_DIRECTORY='/Users/danramage/tmp/wq_feeds'
else:
  LOGFILE='/var/log/wq_rest/devapiflaskvuesite.log'
  DATA_DIRECTORY='/var/nfs/wq_feeds'

VALID_UPDATE_ADDRESSES = ['127.0.0.1', '129.252.139.113', '129.252.139.170']

if not PYCHARM_DEBUG:
  SITES_CONFIG = {
    'myrtlebeach':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'sc_wq/vb_engine/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'sc_wq/vb_engine/monitorstations/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'sc_wq/vb_engine/monitorstations')
      },
    'surfside':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'sc_wq/vb_engine/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'sc_wq/vb_engine/monitorstations/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'sc_wq/vb_engine/monitorstations')
      },
    'sarasota':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'fl_wq/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'fl_wq/monitorstations/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'fl_wq/monitorstations'),
        'ripcurrents': os.path.join(DATA_DIRECTORY, 'fl_wq/nwsforecasts/forecasts.json')
      },
    'charleston':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'charleston/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'charleston/monitorstations/beach_advisories.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'charleston/monitorstations')
      },
    'killdevilhills':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'northcarolina/killdevilhills/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY,
                                      'northcarolina/killdevilhills/monitorstations/kdh_beach_advisories.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'northcarolina/killdevilhills/monitorstations')
      },
    'follybeach':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'follybeach/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'follybeach/monitorstations/beach_advisories.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'follybeach/monitorstations'),
        'camera_statistics': '',
        'shellfish_closures': os.path.join(DATA_DIRECTORY, 'follybeach/shellfish/shellfish_closures.json'),
        'ripcurrents': os.path.join(DATA_DIRECTORY, 'follybeach/ripcurrent/forecasts.json'),
        'camera_rest': {
          'url': 'https://www.floridaapdata.org/beach/response_beach.php'
        }
      },
    'radioisland':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'northcarolina/radioisland/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY,
                                      'northcarolina/radioisland/monitorstations/radioisland_beach_advisories.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'northcarolina/radioisland/monitorstations')
      },
    'midlands':
      {
        'prediction_file': '',
        'advisory_file': os.path.join(DATA_DIRECTORY, 'sc_rivers/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'sc_rivers/monitorstations')
      },
    'murrellsinlet':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'sc_wq/vb_engine/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'sc_wq/vb_engine/monitorstations/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'sc_wq/vb_engine/monitorstations')
      },

  }
else:
  SITES_CONFIG = {
    'murrellsinlet':
      {
        'prediction_file': '',
        'advisory_file': '',
        'stations_directory': ''
      },
    'myrtlebeach':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'sc_mb/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'sc_mb/monitorstations/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'sc_mb/monitorstations')
      },
    'surfside':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'sc_mb/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'sc_mb/monitorstations/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'sc_mb/monitorstations')
      },
    'charleston':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'charleston/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'charleston/monitorstations/beach_advisories.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'charleston/monitorstations')
      },
    'killdevilhills':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'kdh/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'kdh/monitorstations/kdh_beach_advisories.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'kdh/monitorstations')
      },
    'follybeach':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'FollyBeach-WaterQuality/data/test_outputs/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY,
                                      'FollyBeach-WaterQuality/data/test_outputs/beach_advisories.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'FollyBeach-WaterQuality/data/test_outputs/'),
        'camera_statistics': os.path.join(DATA_DIRECTORY, 'FollyBeach-WaterQuality/data/camera/summary_data.json'),
        'shellfish_closures': os.path.join(DATA_DIRECTORY,
                                           'FollyBeach-WaterQuality/data/shellfish/shellfish_closures.json'),
        'ripcurrents': os.path.join(DATA_DIRECTORY, 'sc_folly_beach/forecasts.json')
      },
    'sarasota':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'fl_wq/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'fl_wq/monitorstations/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'fl_wq/monitorstations'),
        'ripcurrents': os.path.join(DATA_DIRECTORY, 'sarasota/forecasts.json')
      },
    'radioisland':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'radioisland/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'radioisland/monitorstations/radioisland_beach_advisories.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'radioisland/monitorstations')
      },
    'midlands':
      {
        'prediction_file': '',
        'advisory_file': os.path.join(DATA_DIRECTORY, 'sc_rivers/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'sc_rivers/monitorstations')
      },
    'myrtlebeach':
      {
        'prediction_file': os.path.join(DATA_DIRECTORY, 'sc_mb/Predictions.json'),
        'advisory_file': os.path.join(DATA_DIRECTORY, 'sc_mb/monitorstations/beachAdvisoryResults.json'),
        'stations_directory': os.path.join(DATA_DIRECTORY, 'sc_mb/monitorstations')
      },
    'murrellsinlet':
      {
        'prediction_file': '',
        'advisory_file': '',
        'stations_directory': ''
      }

  }

#Number of hours the advisory should be considered valid.
SITE_TYPE_DATA_VALID_TIMEOUTS= {
  'Water Quality': 192,
  'Nowcast': 24,
  'Shellfish': 24,
  'Rip Current': 4
}