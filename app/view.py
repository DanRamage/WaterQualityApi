import os
from flask import request, redirect, render_template, current_app, url_for
from flask.views import View, MethodView
import flask_admin as admin
import flask_login as login
from flask_admin.contrib import sqla
from flask_admin import helpers, expose
from flask_security import Security, SQLAlchemyUserDatastore, \
    login_required, current_user
from sqlalchemy import exc
import requests
import time
import json
import geojson
from datetime import datetime
from wtforms import form, fields, validators
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import exc
from shapely.wkb import loads as wkb_loads
from shapely.wkt import loads as wkt_loads
from config import CURRENT_SITE_LIST, VALID_UPDATE_ADDRESSES, SITES_CONFIG, SITE_TYPE_DATA_VALID_TIMEOUTS

from app import db
from .admin_models import User
from .wq_models import Project_Area, \
  Site_Message, \
  Advisory_Limits, \
  Sample_Site,\
  Sample_Site_Data,\
  Site_Extent,\
  Boundary, \
  Site_Type, \
  Collection_Program_Info, \
  Collection_Program_Info_Mapper, \
  Collection_Program_Type, \
  BeachAmbassador

class SiteGeometry:
  def __init__(self, geom):
    self._geometry = geom

class SiteProperties:
  def __init__(self, **kwargs):
    for key, value in kwargs.items():
      setattr(self, "_{}".format(key), value)


class SiteFeature:
  def __init__(self, geometry, properties):
    self._geometry = SiteGeometry(geometry)
    self._properties = SiteProperties(properties)


def locate_element(list, filter):
  for ndx, x in enumerate(list):
    if filter(x):
      return ndx
  return -1


def build_advisory_feature(sample_site_rec, sample_date, values):
  beachadvisories = {
    'date': '',
    'station': sample_site_rec.site_name,
    'value': ''
  }
  if len(values):
    beachadvisories = {
      'date': sample_date,
      'station': sample_site_rec.site_name,
      'value': values
    }
  feature = {
    'type': 'Feature',
    'geometry': {
      'type': 'Point',
      'coordinates': [sample_site_rec.longitude, sample_site_rec.latitude]
    },
    'properties': {
      'locale': sample_site_rec.description,
      'sign': False,
      'station': sample_site_rec.site_name,
      'epaid': sample_site_rec.epa_id,
      'beach': sample_site_rec.county,
      'desc': sample_site_rec.description,
      'has_advisory': sample_site_rec.has_current_advisory,
      'station_message': sample_site_rec.advisory_text,
      'len': '',
      'test': {
        'beachadvisories': beachadvisories
      }
    }
  }
  extents_json = None
  if len(sample_site_rec.extents):
    extents_json = geojson.Feature(geometry=sample_site_rec.extents[0].wkt_extent, properties={})
    feature['properties']['extents_geometry'] = extents_json

  return feature

def build_site_feature(site_rec):
  feature = {
    'type': 'Feature',
    'geometry': {
      'type': 'Point',
      'coordinates': [site_rec.longitude, site_rec.latitude]
    },
    'properties': {
      'locale': site_rec.description,
      'station': site_rec.site_name,
      'beach': site_rec.county,
      'desc': site_rec.description,
      'station_message': site_rec.advisory_text,
    }
  }
  if site_rec.site_type is not None:
    feature['properties']['site_type'] = site_rec.site_type.name
  return feature


def build_prediction_feature(sample_site_rec, sample_date, model_results):
  tests = []
  if len(model_results):
    for model_result in model_results:
      tests.append({
        'data': model_results['data'],
        'name': model_result['name'],
        'p_level':model_result['p_level'],
        'p_value': model_result['p_value'],
      })
  feature = {
    "type": "Feature",
    'geometry': {
      'type': 'Point',
      'coordinates': [sample_site_rec.longitude, sample_site_rec.latitude]
    },
    "properties": {
      "ensemble": "None",
      'station': sample_site_rec.site_name,
      'desc': sample_site_rec.description,
      'has_advisory': sample_site_rec.has_current_advisory,
      "site_message": {
        "message": "",
        "severity": ""
      },
      'tests': tests
    }
  }
  return feature

def build_feature_collection(features):
  feature_collection = {
    'features': features,
    'type': 'FeatureCollection'
  }
  return feature_collection

class MaintenanceMode(View):
  def dispatch_request(self):
    current_app.logger.debug('IP: %s MaintenanceMode rendered' % (request.remote_addr))
    return render_template("MaintenanceMode.html")

class ShowIntroPage(View):
  def dispatch_request(self):
    current_app.logger.debug('IP: %s intro_page rendered' % (request.remote_addr))
    #return render_template("intro_page.html")
    return render_template("index.html")

class ShowAboutPage(View):
  def __init__(self, site_name="./", page_template='about_page.html'):
    current_app.logger.debug('__init__')
    self.site_name = site_name
    self.page_template = page_template

  def dispatch_request(self):
    start_time = time.time()
    current_app.logger.debug('IP: %s dispatch_request started' % (request.remote_addr))
    try:
      current_app.logger.debug('Site: %s rendered.' % (self.site_name))
      rendered_template = render_template(self.page_template,
                             site_name=self.site_name)
    except Exception as e:
      current_app.logger.exception(e)
      rendered_template = render_template(self.page_template,
                             site_name=self.site_name)

    current_app.logger.debug('dispatch_request finished in %f seconds' % (time.time()-start_time))
    return rendered_template


class CameraPage(View):
  def __init__(self, site_name):
    current_app.logger.debug('__init__')
    self.site_name = site_name
    self.page_template = 'camera_page_template.html'

class SitePage(View):
  def __init__(self, site_name):
    current_app.logger.debug('__init__')
    self.site_name = site_name
    self.page_template = 'index_template.html'
    self._data_types = {}

  def get_site_message(self):
    current_app.logger.debug('IP: %s get_site_message started' % (request.remote_addr))
    start_time = time.time()
    rec = db.session.query(Site_Message)\
      .join(Project_Area, Project_Area.id == Site_Message.site_id)\
      .filter(Project_Area.area_name == self.site_name).first()
    current_app.logger.debug('get_site_message finished in %f seconds' % (time.time()-start_time))
    return rec

  def get_program_info(self):
    current_app.logger.debug('get_program_info started')
    start_time = time.time()
    program_info = {}
    try:
      #Get the advisroy limits
      limit_recs = db.session.query(Advisory_Limits)\
        .join(Project_Area, Project_Area.id == Advisory_Limits.site_id)\
        .filter(Project_Area.area_name == self.site_name)\
        .order_by(Advisory_Limits.min_limit).all()
      limits = {}
      for limit in limit_recs:
        limits[limit.limit_type] = {
          'min_limit': limit.min_limit,
          'max_limit': limit.max_limit,
          'icon': limit.icon
        }
      program_info = {
          'advisory_limits': limits,
        }
    except Exception as e:
      current_app.logger.exception(e)
    #Get the program info

    current_app.logger.debug('get_program_info finished in %f seconds' % (time.time()-start_time))
    return program_info

  def get_shellfish_data(self, site, feature):
    if self.site_name == 'follybeach':
      shellfish_data, ret_val = get_data_file(SITES_CONFIG[self.site_name]['shellfish_closures'])
      #DHEC shellfish sites are coded: "Region-Site", so split the name so we can get the region.
      region,site_name = site.site_name.split('-')
      json_data = json.loads(shellfish_data)
      if region in json_data:
        closure_data = json_data[region]
        advisory = False
        if closure_data['Storm_Closure'].lower() == 'closed':
          advisory = True
        feature['properties']['station'] = site_name
        feature['properties']['region'] = region
        feature['properties']['has_advisory'] = advisory
        feature['properties']['date_time_last_check'] = closure_data['date_time_last_check']

  def get_rip_current_data(self, site, feature):
    if self.site_name == 'follybeach':
      #So we don't keep reloading and coverting the json file, we save the first load of it in a dictionary.
      if 'ripcurrent' in self._data_types:
        json_data = self._data_types['ripcurrent']
      else:
        ripcurrent_data, ret_val = get_data_file(SITES_CONFIG[self.site_name]['ripcurrents'])
        json_data = json.loads(ripcurrent_data)
        self._data_types['ripcurrent'] = json_data

      feat_properties = feature['properties']
      for station in json_data['features']:
        if station['properties']['description'] == feat_properties['station']:
          feat_properties['date'] = station['properties']['date']
          feat_properties['flag'] = station['properties']['flag']
          feat_properties['level'] = station['properties']['level']
          break
      return
  def get_data(self):
    current_app.logger.debug('get_data started')
    start_time = time.time()
    data = {}
    try:
      if self.site_name in SITES_CONFIG:
        prediction_data, pred_ret_code = get_data_file(SITES_CONFIG[self.site_name]['prediction_file'])
        advisory_data, adv_ret_code = get_data_file(SITES_CONFIG[self.site_name]['advisory_file'])
        pred_json = adv_data = None
        try:
          current_app.logger.debug("Creating prediction data JSON.")
          pred_json = json.loads(prediction_data)
          current_app.logger.debug("Creating advisory data JSON.")
          adv_data = json.loads(advisory_data)
        except Exception as e:
          current_app.logger.exception(e)
        data = {
          'prediction_data': pred_json,
          'advisory_data': adv_data,
          'sites': None
        }
        #Query the Sample_Site table to get any specific settings we need for the map.
        #Currently for the Charleston site, we want to disable the Advisory in the site popup
        #since they do not issue advisories.
        sample_sites = db.session.query(Sample_Site) \
          .join(Project_Area, Project_Area.id == Sample_Site.project_site_id) \
          .filter(Project_Area.area_name == self.site_name).all()

        build_advisory_from_db = False
        if adv_ret_code == 404:
          del(data['advisory_data']['contents'])
          data['advisory_data']['type'] = "FeatureCollection"
          data['advisory_data']['features'] = []
          data['advisory_data']['status']['http_code'] = 200
          build_advisory_from_db = True

        build_blank_predictions = False
        if pred_ret_code == 404:
          data['prediction_data']['contents'] = {
            'run_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'testDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stationData': {'features': []}
          }
          data['prediction_data']['status']['http_code'] = 200
          build_blank_predictions = True

        for site in sample_sites:
          #If the site doesn't have a type, or it's Default(water quality site).
          if site.site_type is None or site.site_type.name == 'Water Quality':
            if not build_advisory_from_db:
              advisory_data = data['advisory_data']['features']
              for site_data in advisory_data:
                if site_data['properties']['station'] == site.site_name:
                  site_data['properties']['issues_advisories'] = site.issues_advisories
            else:
              feature = build_advisory_feature(site, datetime.now(), [])
              feature['issues_advisories'] = site.issues_advisories
              data['advisory_data']['features'].append(feature)
            if build_blank_predictions:
              feature = build_prediction_feature(site, datetime.now(), [])
              data['prediction_data']['contents']['stationData']['features'].append(feature)
          else:
            feature = build_site_feature(site)
            if data['sites'] is None:
              data['sites'] = build_feature_collection([])

            if site.site_type is not None and site.site_type.name == 'Shellfish':
              self.get_shellfish_data(site, feature)
            elif site.site_type is not None and site.site_type.name == 'Rip Current':
              self.get_rip_current_data(site, feature)
            data['sites']['features'].append(feature)

        #Query the database to see if we have any temporary popup sites.
        popup_sites = db.session.query(Sample_Site) \
          .join(Project_Area, Project_Area.id == Sample_Site.project_site_id) \
          .filter(Project_Area.area_name == self.site_name)\
          .filter(Sample_Site.temporary_site == True).all()
        if len(popup_sites):
          advisory_data_features = data['advisory_data']['features']
          for site in popup_sites:
            sample_date = site.row_entry_date
            sample_value = []
            if len(site.site_data):
              sample_date = site.site_data[0].sample_date
              sample_value.append(site.site_data[0].sample_value)
            feature = build_advisory_feature(site, sample_date, sample_value)
            advisory_data_features.append(feature)
      else:
        current_app.logger.error("Site: %s does not exist" % (self.site_name))
    except Exception as e:
      current_app.logger.exception(e)
    current_app.logger.debug('get_data finished in %f seconds' % (time.time()-start_time))
    return data

  def dispatch_request(self):
    start_time = time.time()
    current_app.logger.debug('IP: %s dispatch_request started' % (request.remote_addr))
    site_message = self.get_site_message()
    program_info = self.get_program_info()
    data = self.get_data()
    try:
      current_app.logger.debug('Site: %s rendered.' % (self.site_name))
      rendered_template = render_template(self.page_template,
                             site_message=site_message,
                             site_name=self.site_name,
                             wq_site_bbox='',
                             sampling_program_info=program_info,
                             data=data)
    except Exception as e:
      current_app.logger.exception(e)
      rendered_template = render_template(self.page_template,
                               site_message='',
                               site_name=self.site_name,
                               wq_site_bbox='',
                               sampling_program_info={},
                               data={})

    current_app.logger.debug('dispatch_request finished in %f seconds' % (time.time()-start_time))
    return rendered_template

class MyrtleBeachPage(SitePage):
  def __init__(self):
    current_app.logger.debug('IP: %s MyrtleBeachPage __init__' % (request.remote_addr))
    SitePage.__init__(self, 'myrtlebeach')
    self.page_template = 'mb_index_page.html'

class MBAboutPage(ShowAboutPage):
  def __init__(self):
    current_app.logger.debug('IP: %s MBAboutPage __init__' % (request.remote_addr))
    ShowAboutPage.__init__(self, 'myrtlebeach', 'sc_about_page.html')



class SarasotaPage(SitePage):
  def __init__(self):
    current_app.logger.debug('IP: %s SarasotaPage __init__' % (request.remote_addr))
    SitePage.__init__(self, 'sarasota')
    self.page_template = 'sarasota_index_page.html'

class SarasotaAboutPage(ShowAboutPage):
  def __init__(self):
    current_app.logger.debug('IP: %s SarasotaAboutPage __init__' % (request.remote_addr))
    ShowAboutPage.__init__(self, 'sarasota', 'fl_about_page.html')

class CharlestonPage(SitePage):
  def __init__(self):
    current_app.logger.debug('IP: %s CharlestonPage __init__' % (request.remote_addr))
    SitePage.__init__(self, 'charleston')
    self.page_template = 'chs_index_page.html'

class CHSAboutPage(ShowAboutPage):
  def __init__(self):
    current_app.logger.debug('IP: %s SCAboutPage __init__' % (request.remote_addr))
    ShowAboutPage.__init__(self, 'charleston', 'sc_about_page.html')

class KillDevilHillsPage(SitePage):
  def __init__(self):
    current_app.logger.debug('IP: %s KillDevilHillsPage __init__' % (request.remote_addr))
    SitePage.__init__(self, 'killdevilhills')
    self.page_template = 'kdh_index_page.html'

class KDHAboutPage(ShowAboutPage):
  def __init__(self):
    current_app.logger.debug('IP: %s NCAboutPage __init__' % (request.remote_addr))
    ShowAboutPage.__init__(self, 'killdevilhills', 'nc_about_page.html')

class FollyBeachShowIntroPage(View):
  def dispatch_request(self):
    current_app.logger.debug('IP: %s follybeach_intro_page rendered' % (request.remote_addr))
    return render_template("folly_beach_intro.html")


class FollyBeachPage(SitePage):
  def __init__(self):
    current_app.logger.debug('IP: %s FollyBeachPage __init__' % (request.remote_addr))
    SitePage.__init__(self, 'follybeach')
    self.page_template = 'follybeach_index_page.html'

class FollyBeachAboutPage(ShowAboutPage):
  def __init__(self):
    current_app.logger.debug('IP: %s FollyBeachAboutPage __init__' % (request.remote_addr))
    ShowAboutPage.__init__(self, 'follybeach', 'sc_about_page.html')

class FollyBeachCameraPage(CameraPage):
  def __init__(self, **kwargs):
    current_app.logger.debug('IP: %s FollyBeachCameraPage __init__' % (request.remote_addr))
    CameraPage.__init__(self, 'follybeach')
    self.page_template = 'camera_page_template.html'
  def dispatch_request(self, cameraname):
    start_time = time.time()
    current_app.logger.debug('IP: %s FollyBeachPage dispatch_request for camera: %s' % (request.remote_addr, cameraname))

    return render_template("follybeach_camera_page_template.html", cameraname=cameraname)

def get_data_file(filename):
  current_app.logger.debug("get_data_file Started.")

  try:
    current_app.logger.debug("Opening file: %s" % (filename))
    with open(filename, 'r') as data_file:
      results = data_file.read()
      ret_code = 200

  except (Exception, IOError) as e:
    current_app.logger.exception(e)

    ret_code = 404
    results = json.dumps({'status': {'http_code': ret_code},
                    'contents': None
                    })


  current_app.logger.debug("get_data_file Finished.")

  return results,ret_code

class BaseAPI(MethodView):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    return
  def parse_request_args(self):
    return
  def json_error_response(self, error_code, error_message):
    json_error = {}
    json_error['error'] = {
      'code': error_code,
      'message': error_message
    }
    return json_error

class PredictionsAPI(MethodView):
  def get(self, sitename=None):
    start_time = time.time()
    current_app.logger.debug('IP: %s PredictionsAPI get for site: %s' % (request.remote_addr, sitename))
    ret_code = 404
    results = None

    if sitename == 'myrtlebeach':
      results, ret_code = get_data_file(SC_MB_PREDICTIONS_FILE)
    elif sitename == 'sarasota':
      results, ret_code = get_data_file(FL_SARASOTA_PREDICTIONS_FILE)
    elif sitename == 'charleston':
      results, ret_code = get_data_file(SC_CHS_PREDICTIONS_FILE)
    elif sitename == 'follybeach':
      results, ret_code = get_data_file(SC_FOLLYBEACH_PREDICTIONS_FILE)

    else:
      results = json.dumps({'status': {'http_code': ret_code},
                    'contents': None
                    })

    current_app.logger.debug('PredictionsAPI get for site: %s finished in %f seconds' % (sitename, time.time() - start_time))
    return (results, ret_code, {'Content-Type': 'Application-JSON'})


class BacteriaDataAPI(MethodView):
  def get(self, sitename=None):
    start_time = time.time()
    current_app.logger.debug('IP: %s BacteriaDataAPI get for site: %s' % (request.remote_addr, sitename))
    ret_code = 404
    results = None

    if sitename == 'myrtlebeach':
      results, ret_code = get_data_file(SC_MB_ADVISORIES_FILE)
      #Wrap the results in the status and contents keys. The app expects this format.
      json_ret = {'status': {'http_code': ret_code},
                  'contents': json.loads(results)}
      results = json.dumps(json_ret)

    elif sitename == 'sarasota':
      results,ret_code = get_data_file(FL_SARASOTA_ADVISORIES_FILE)
      #Wrap the results in the status and contents keys. The app expects this format.
      json_ret = {'status' : {'http_code': ret_code},
                  'contents': json.loads(results)}
      results = json.dumps(json_ret)

    elif sitename == 'charleston':
      results,ret_code = get_data_file(SC_CHS_ADVISORIES_FILE)
      #Wrap the results in the status and contents keys. The app expects this format.
      json_ret = {'status' : {'http_code': ret_code},
                  'contents': json.loads(results)}
      results = json.dumps(json_ret)

    else:
      results = json.dumps({'status': {'http_code': ret_code},
                    'contents': None
                    })

    current_app.logger.debug('BacteriaDataAPI get for site: %s finished in %f seconds' % (sitename, time.time() - start_time))
    return (results, ret_code, {'Content-Type': 'Application-JSON'})


class StationDataAPI(MethodView):
  def post(self, sitename=None, station_name=None):

    results = ""
    ret_code = 404
    #Only allow IP addresses that are approved to update/insert data into the database.
    if request.remote_addr in VALID_UPDATE_ADDRESSES:
      #Is the site a valid on?
      if sitename in CURRENT_SITE_LIST:
        sampledate = None
        if 'sampledate' in request.args:
          sampledate = request.args['sampledate']
          try:
            start_date = datetime.strptime(sampledate, '%Y-%m-%d %H:%M:%S')
          except (ValueError, Exception) as e:
            try:
              start_date = datetime.strptime(sampledate, '%Y-%m-%dT%H:%M:%SZ')
            except (ValueError, Exception) as e:
              current_app.logger.exception(e)
              sampledate = None
              ret_code = 400
        value = None
        if 'value' in request.args:
          try:
            value = float(request.args['value'])
          except (ValueError, Exception) as e:
            current_app.logger.exception(e)
            value = None
            ret_code = 400

        if sampledate is not None and value is not None:
          current_app.logger.debug('IP: %s StationDataAPI post data for site: %s station: %s date: %s value: %f' % \
                                   (request.remote_addr, sitename, station_name, sampledate, value))
          ret_code = 200
          sample_site_id = db.session.query(Sample_Site.id)\
            .filter(Sample_Site.site_name==station_name)\
            .scalar()
          if sample_site_id is not None:
            #Check if the entry date exists, if it doesn't we add new record, otherwise
            #update.
            sample_data = db.session.query(Sample_Site_Data)\
              .filter(Sample_Site_Data.sample_date == sampledate)\
              .filter(Sample_Site_Data.site_id==sample_site_id).first()
            if sample_data is None:
              current_app.logger.debug("Adding record.")
              sample_data = Sample_Site_Data(row_entry_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                             sample_date=sampledate,
                                             sample_value=value,
                                             site_id=sample_site_id)
              db.session.add(sample_data)
            else:
              current_app.logger.debug("Updating record.")
              sample_data.row_update_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
              sample_data.sample_value = value
            db.session.commit()
            results = json.dumps({'status': {'http_code': ret_code},
                          'contents': None
                          })
          else:
            current_app.logger.error("Site: %s does not exist in database." % (station_name))

        else:
          current_app.logger.error("IP: %s Site: %s Station: %s has one more invalid arguments. Args: %s"%\
                                   (request.remote_addr, sitename, station_name, request.args))
      else:
        current_app.logger.warning(
          'IP: %s Site: %s is invalid. Args: %s' % \
          (request.remote_addr, sitename, request.args))


    else:
      current_app.logger.warning('IP: %s is not in the valid update list, request cancelled. Site: %s Station: %s Args: %s' %\
                               (request.remote_addr, sitename, station_name, request.args))

    return (results, ret_code, {'Content-Type': 'Application-JSON'})

  def get(self, sitename=None, station_name=None):
    start_date = None
    ret_code = 404
    results = ''
    if 'startdate' in request.args:
      start_date = request.args['startdate']
      try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
      except (ValueError, Exception) as e:
        current_app.logger.exception(e)
        start_date = None
        ret_code = 400
    if start_date is not None:
      current_app.logger.debug('IP: %s StationDataAPI get for site: %s station: %s date: %s' % (request.remote_addr, sitename, station_name, start_date))
      ret_code = 404
      if sitename in SITES_CONFIG:
        results = self.get_requested_station_data(station_name, request, SITES_CONFIG[sitename]['stations_directory'])
        ret_code = 200
      else:
        results = json.dumps({'status': {'http_code': ret_code},
                      'contents': None
                      })

    return (results, ret_code, {'Content-Type': 'Application-JSON'})

  def get_requested_station_data(self, station, request, station_directory):
    start_time = time.time()
    ret_code = 404
    current_app.logger.debug("get_requested_station_data Started")

    json_data = {'status': {'http_code': 404},
               'contents': {}}

    start_date = None
    if 'startdate' in request.args:
      start_date = request.args['startdate']
    current_app.logger.debug("Station: %s Start Date: %s" % (station, start_date))

    feature = None
    try:
      filepath = os.path.join(station_directory, '%s.json' % (station))
      current_app.logger.debug("Opening station file: %s" % (filepath))

      with open(filepath, "r") as json_data_file:
        stationJson = geojson.load(json_data_file)

      resultList = []
      #If the client passed in a startdate parameter, we return only the test dates >= to it.
      if start_date:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        advisoryList = stationJson['properties']['test']['beachadvisories']
        for ndx in range(len(advisoryList)):
          try:
            tst_date_obj = datetime.strptime(advisoryList[ndx]['date'], "%Y-%m-%d")
          except ValueError as e:
            try:
              tst_date_obj = datetime.strptime(advisoryList[ndx]['date'], "%Y-%m-%d %H:%M:%S")
            except ValueError as e:
              try:
                tst_date_obj = datetime.strptime(advisoryList[ndx]['date'], "%Y-%m-%dT%H:%M:%SZ")
              except ValueError as e:
                current_app.logger.exception(e)

          if tst_date_obj >= start_date_obj:
            resultList = advisoryList[ndx:]
            break
      else:
        resultList = stationJson['properties']['test']['beachadvisories'][-1]

      properties = {}
      properties['desc'] = stationJson['properties']['desc']
      properties['station'] = stationJson['properties']['station']
      properties['test'] = {'beachadvisories' : resultList}

      feature = geojson.Feature(id=station, geometry=stationJson['geometry'], properties=properties)
      ret_code = 200

    except (IOError, ValueError, Exception) as e:
      current_app.logger.exception(e)
    try:
      if feature is None:
        feature = geojson.Feature(id=station)

      json_data = {'status': {'http_code': ret_code},
                  'contents': feature
                  }
    except Exception as e:
      current_app.logger.exception(e)


    results = geojson.dumps(json_data, separators=(',', ':'))
    current_app.logger.debug("get_requested_station_data finished in %s seconds" % (time.time() - start_time))
    return results

class StationDataUpdateAPI(MethodView):
  def get(self, sitename=None, station_name=None):
    start_date = ''
    if 'startdate' in request.args:
      start_date = request.args['startdate']

    current_app.logger.debug('IP: %s StationDataAPI get for site: %s station: %s date: %s' % (request.remote_addr, sitename, station_name, start_date))
    ret_code = 404

    if sitename == 'myrtlebeach':
      results = self.set_station_data(station_name, request, SC_MB_STATIONS_DATA_DIR)
      ret_code = 200

    elif sitename == 'sarasota':
      results = self.set_station_data(station_name, request, FL_SARASOTA_STATIONS_DATA_DIR)
      ret_code = 200

    elif sitename == 'charleston':
      results = self.set_station_data(station_name, request, SC_CHS_STATIONS_DATA_DIR)
      ret_code = 200

    else:
      results = json.dumps({'status': {'http_code': ret_code},
                    'contents': None
                    })

    return (results, ret_code, {'Content-Type': 'Application-JSON'})

  def set_station_data(self, station, request, station_directory):
    start_time = time.time()
    ret_code = 404
    current_app.logger.debug("set_station_data Started")

    json_data = {'status': {'http_code': 404},
               'contents': {}}

    start_date = None
    if 'startdate' in request.args:
      start_date = request.args['startdate']

    current_app.logger.debug("Station: %s Test Date: %s Value: %f" % (station, start_date, value))

    current_app.logger.debug("set_station_data finished in %f seconds" % (time.time()-start_time))
    return

class CameraDataAPI(MethodView):
  def get(self, sitename=None, cameraname=None):
    start_time = time.time()
    current_app.logger.debug('IP: %s CameraDataAPI get camera data: %s for site: %s' % (request.remote_addr, cameraname, sitename))
    ret_code = 404
    results = None

    results = json.dumps({'status': {'http_code': ret_code},
                          'contents': None
                          })
    try:
      if sitename == 'follybeach':
        file_results, ret_code = get_data_file(SITES_CONFIG[sitename]['camera_statistics'])
        camera_json = json.loads(file_results)
        results = json.dumps(camera_json[cameraname])

    except Exception as e:
      current_app.logger.exception(e)
    current_app.logger.debug('CameraDataAPI get camera data: %s site: %s finished in %f seconds' % (cameraname, sitename, time.time() - start_time))
    return (results, ret_code, {'Content-Type': 'Application-JSON'})

# Define login and registration forms (for flask-login)
class LoginForm(form.Form):
    login = fields.StringField(validators=[validators.DataRequired()])
    password = fields.PasswordField(validators=[validators.DataRequired()])

    def validate_login(self, field):
      user = self.get_user()

      if user is None:
          raise validators.ValidationError('Invalid user')

      # we're comparing the plaintext pw with the the hash from the db
      if not check_password_hash(user.password, self.password.data):
      # to compare plain text passwords use
      # if user.password != self.password.data:
          raise validators.ValidationError('Invalid password')

    def get_user(self):
      return db.session.query(User).filter_by(login=self.login.data).first()


"""
class RegistrationForm(form.Form):
    login = fields.StringField(validators=[validators.required()])
    email = fields.StringField()
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
      if db.session.query(User).filter_by(login=self.login.data).count() > 0:
        raise validators.ValidationError('Duplicate username')
"""

class base_view(sqla.ModelView):
  """
  This view is used to update some common columns across all the tables used.
  Now it's mostly the row_entry_date and row_update_date.
  """
  def on_model_change(self, form, model, is_created):
    start_time = time.time()
    current_app.logger.debug("IP: %s User: %s on_model_change started" % (request.remote_addr, current_user.login))

    entry_time = datetime.utcnow()
    if is_created:
      model.row_entry_date = entry_time.strftime("%Y-%m-%d %H:%M:%S")
    else:
      model.row_update_date = entry_time.strftime("%Y-%m-%d %H:%M:%S")

    sqla.ModelView.on_model_change(self, form, model, is_created)

    current_app.logger.debug("IP: %s User: %s on_model_change finished in %f seconds" % (request.remote_addr, current_user.login, time.time() - start_time))

  def is_accessible(self):
    """
    This checks to make sure the user is active and authenticated and is a superuser. Otherwise
    the view is not accessible.
    :return:
    """
    if not current_user.is_active or not current_user.is_authenticated:
      return False

    if current_user.has_role('superuser'):
      return True

    return False

class AdminUserModelView(base_view):
  """
  This view handles the administrative user editing/creation of users.
  """
  form_extra_fields = {
    'password': fields.PasswordField('Password')
  }
  column_list = ('login', 'first_name', 'last_name', 'email', 'active', 'roles', 'row_entry_date', 'row_update_date')
  form_columns = ('login', 'first_name', 'last_name', 'email', 'password', 'active', 'roles')

  def on_model_change(self, form, model, is_created):
    """
    If we're creating a new user, hash the password entered, if we're updating, check if password
    has changed and then hash that.
    :param form:
    :param model:
    :param is_created:
    :return:
    """
    start_time = time.time()
    current_app.logger.debug(
      'IP: %s User: %s AdminUserModelView on_model_change started.' % (request.remote_addr, current_user.login))
    # Hash the password text if we're creating a new user.
    if is_created:
      model.password = generate_password_hash(form.password.data)
    # If this is an update, check to see if password has changed and if so hash the form password.
    else:
      hashed_pwd = generate_password_hash(form.password.data)
      if hashed_pwd != model.password:
        model.password = hashed_pwd

    current_app.logger.debug('IP: %s User: %s AdminUserModelView create_model finished in %f seconds.' % (
    request.remote_addr, current_user.login, time.time() - start_time))

class BasicUserModelView(AdminUserModelView):
  """
  Basic user view. A simple user only gets access to their data record to edit. No creating or deleting.
  """
  column_list = ('login', 'first_name', 'last_name', 'email')
  form_columns = ('login', 'first_name', 'last_name', 'email', 'password')
  can_create = False  # Don't allow a basic user ability to add a new user.
  can_delete = False  # Don't allow user to delete records.

  def get_query(self):
    # Only return the record that matches the logged in user.
    return super(AdminUserModelView, self).get_query().filter(User.login == login.current_user.login)

  def is_accessible(self):
    if current_user.is_active and current_user.is_authenticated and not current_user.has_role('superuser'):
      return True
    return False

class RolesView(base_view):
  """
  View into the user Roles table.
  """
  column_list = ['name', 'description']
  form_columns = ['name', 'description']


# Create customized model view class
class MyModelView(sqla.ModelView):

  def is_accessible(self):
    return login.current_user.is_authenticated



# Create customized index view class that handles login & registration
class MyAdminIndexView(admin.AdminIndexView):

    @expose('/')
    def index(self):
        current_app.logger.debug("IP: %s Admin index page" % (request.remote_addr))
        if not login.current_user.is_authenticated:
          current_app.logger.debug("User: %s is not authenticated" % (login.current_user))
          return redirect(url_for('.login_view'))
        return super(MyAdminIndexView, self).index()

    @expose('/login/', methods=('GET', 'POST'))
    def login_view(self):
        # handle user login
        current_app.logger.debug("IP: %s Login page" % (request.remote_addr))
        form = LoginForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = form.get_user()
            login.login_user(user)
        else:
          current_app.logger.debug("IP: %s User: %s is not authenticated" % (request.remote_addr, form.login.data))
        if login.current_user.is_authenticated:
            return redirect(url_for('.index'))
        #link = '<p>Don\'t have an account? <a href="' + url_for('.register_view') + '">Click here to register.</a></p>'
        self._template_args['form'] = form
        #self._template_args['link'] = link
        return super(MyAdminIndexView, self).index()
    """
    @expose('/register/', methods=('GET', 'POST'))
    def register_view(self):
        form = RegistrationForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = User()

            form.populate_obj(user)
            # we hash the users password to avoid saving it as plaintext in the db,
            # remove to use plain text:
            user.password = generate_password_hash(form.password.data)

            db.session.add(user)
            db.session.commit()

            login.login_user(user)
            return redirect(url_for('.index'))

        link = '<p>Already have an account? <a href="' + url_for('.login_view') + '">Click here to log in.</a></p>'
        self._template_args['form'] = form
        self._template_args['link'] = link
        return super(MyAdminIndexView, self).index()
    """
    @expose('/logout/')
    def logout_view(self):
        current_app.logger.debug("IP: %s Logout page" % (request.remote_addr))
        login.logout_user()
        return redirect(url_for('.index'))


class project_type_view(base_view):
  column_list = ['name', 'row_entry_date', 'row_update_date']
  form_columns = ['name']

class project_area_view(base_view):
  column_list = ['area_name', 'display_name', 'row_entry_date', 'row_update_date']
  form_columns = ['area_name', 'display_name']

class site_message_view(base_view):
  column_list = ['site', 'message', 'row_entry_date', 'row_update_date']
  form_columns = ['site', 'message']

  def is_accessible(self):
    if current_user.is_active and current_user.is_authenticated:
      return True
    return False

class site_message_level_view(base_view):
  column_list = ['message_level', 'row_entry_date', 'row_update_date']
  form_columns = ['message_level']

class advisory_limits_view(base_view):
  column_list = ['site', 'min_limit', 'max_limit', 'icon', 'limit_type', 'row_entry_date', 'row_update_date']
  form_columns = ['site', 'min_limit', 'max_limit', 'icon', 'limit_type']

class sample_site_view(base_view):
  """
  View for the Sample_Site table.
  """
  column_list = ['project_site', 'site_name', 'site_type', 'latitude', 'longitude', 'description', 'epa_id', 'city', 'county', 'post_code', 'state_abbreviation', 'issues_advisories', 'has_current_advisory', 'advisory_text', 'boundaries', 'temporary_site', 'site_data', 'row_entry_date', 'row_update_date']
  form_columns = ['project_site', 'site_name', 'site_type', 'latitude', 'longitude', 'description', 'epa_id', 'city', 'county', 'post_code', 'state_abbreviation', 'site_data','issues_advisories', 'has_current_advisory', 'advisory_text', 'boundaries', 'temporary_site']
  column_filters = ['project_site']

  def on_model_change(self, form, model, is_created):
    """
    When a new record is created or editing, we want to take the values in the lat/long field
    and populate the wkt_location field.
    :param form:
    :param model:
    :param is_created:
    :return:
    """
    start_time = time.time()
    current_app.logger.debug('IP: %s User: %s popup_site_view on_model_change started.' % (request.remote_addr, current_user.login))

    if is_created:
      entry_time = datetime.utcnow()
      model.row_entry_date = entry_time.strftime("%Y-%m-%d %H:%M:%S")

    model.user = login.current_user
    """
    if len(model.wkt_location) and form.longitude.data is None and form.latitude.data is None:
      points = model.wkt_location.replace('POINT(', '').replace(')', '')
      longitude,latitude = points.split(' ')
      form.longitude.data = float(longitude)
      form.latitude.data = float(latitude)
    else:
      wkt_location = "POINT(%s %s)" % (form.longitude.data, form.latitude.data)
      model.wkt_location = wkt_location
    """
    base_view.on_model_change(self, form, model, is_created)

    current_app.logger.debug('IP: %s User: %s popup_site_view on_model_change finished in %f seconds.' % (request.remote_addr, current_user.login, time.time() - start_time))

class site_type_view(base_view):
  column_list = ['name', 'row_entry_date', 'row_update_date']
  form_columns = ['name']

class collection_program_info(base_view):
  column_list = ['id', 'program', 'url', 'description', 'program_type', 'state', 'state_abbreviation', 'sites', 'row_entry_date', 'row_update_date']
  form_columns = ['program', 'url', 'description', 'program_type', 'state', 'state_abbreviation', 'sites', 'row_entry_date', 'row_update_date']
  column_filters = ['program']

class collection_program_type(base_view):
  column_list = ['id', 'program_type']
  form_columns = ['program_type']
  column_filters = ['program_type']

class beach_ambassador_sites(base_view):
  column_list = ['id', 'bcrs_id', 'sample_site_name', 'site_url', 'row_entry_date', 'row_update_date']
  form_columns = ['bcrs_id', 'sample_site_name', 'site_url', 'row_entry_date', 'row_update_date']
  column_filters = ['bcrs_id', 'sample_site_name', 'site_url', 'row_entry_date', 'row_update_date']


class wktTextField(fields.TextAreaField):
  def process_data(self, value):
    self.data = wkb_loads(value)

class boundary_view(base_view):
  #Instead of showing the binary of the wkb_boundary field, we convert to the wkt
  #and diplay it.
  #Formatter to convert the wkb to wkt for display.
  def _wkb_to_wkt(view, context, model, name):
    wkt = wkb_loads(model.wkb_boundary)
    return wkt

  form_extra_fields = {
    'wkb_boundary': wktTextField('Boundary Polygon')
  }
  column_formatters = {
    'wkb_boundary': _wkb_to_wkt
  }
  column_list = ['project_site', 'boundary_name', 'wkb_boundary', 'row_entry_date', 'row_update_date']
  form_columns = ['project_site', 'boundary_name', 'wkb_boundary']
  column_filters = ['project_site']

  def on_model_change(self, form, model, is_created):
    """
    Handle the wkt to wkb to store in the database.
    :param form:
    :param model:
    :param is_created:
    :return:
    """
    start_time = time.time()
    current_app.logger.debug(
      'IP: %s User: %s boundary_view on_model_change started.' % (request.remote_addr, current_user.login))
    geom = wkt_loads(form.wkb_boundary.data)
    model.wkb_boundary = geom.wkb

    base_view.on_model_change(self, form, model, is_created)

    current_app.logger.debug('IP: %s User: %s boundary_view create_model finished in %f seconds.' % (
    request.remote_addr, current_user.login, time.time() - start_time))


class site_extent_view(base_view):
  column_list = ['sample_site', 'extent_name', 'wkt_extent', 'row_entry_date', 'row_update_date']
  form_columns = ['sample_site', 'extent_name', 'wkt_extent']

class popup_site_view(base_view):

  column_list = ['project_site', 'site_name', 'latitude', 'longitude', 'description', 'advisory_text']
  form_columns = ['project_site', 'site_name', 'latitude', 'longitude', 'description', 'advisory_text']
  column_filters = ['project_site']

  def on_model_change(self, form, model, is_created):
    start_time = time.time()
    current_app.logger.debug('IP: %s User: %s popup_site_view on_model_change started.' % (request.remote_addr, current_user.login))

    model.temporary_site = True
    model.wkt_location = "POINT(%s %s)" % (form.longitude.data, form.latitude.data)
    base_view.on_model_change(self, form, model, is_created)

    current_app.logger.debug('IP: %s User: %s popup_site_view on_model_change finished in %f seconds.' % (request.remote_addr, current_user.login, time.time() - start_time))

  def get_query(self):
    #For this view we only return the sites that are temporary, not the main sampleing sites.
    return super(popup_site_view, self).get_query().filter(Sample_Site.temporary_site == True)

  def is_accessible(self):
    if current_user.is_active and current_user.is_authenticated:
      return True
    return False

class sample_site_data_view(base_view):
  column_list=['sample_site_name', 'sample_date', 'sample_value', 'row_entry_date', 'row_update_date']
  form_columns=['sample_site_name', 'sample_date', 'sample_value']
  column_filters = ['sample_site_name']



class DefaultClickPopup(View):
  def __init__(self, sitename=None, cameraname=None):
    current_app.logger.debug('__init__')

  def dispatch_request(self, sitename=None, cameraname=None):
    start_time = time.time()
    current_app.logger.debug('IP: %s dispatch_request started' % (request.remote_addr))
    try:
      current_app.logger.debug('Site: %s rendered.' % (self.site_name))
      rendered_template = render_template('default_popup_test.html')
    except Exception as e:
      current_app.logger.exception(e)
      rendered_template = render_template('default_popup_test.html')

    current_app.logger.debug('dispatch_request finished in %f seconds' % (time.time()-start_time))
    return rendered_template


class SiteMapPage(View):
  def __init__(self, page_template=None):
    self.page_template = page_template
    if self.page_template is None:
      self.page_template = 'map_page.html'

  def dispatch_request(self):
    sitename = request.endpoint
    start_time = time.time()
    current_app.logger.debug('IP: %s SiteMapPage dispatch_request get for site: %s' % (request.remote_addr, sitename))
    ret_code = 404
    results = None

    try:
      current_app.logger.debug('Site: %s rendered.' % (sitename))
      rendered_template = render_template(self.page_template,
                                          sitename=sitename)
    except Exception as e:
      current_app.logger.exception(e)
      rendered_template = render_template(self.page_template,
                                          sitename=sitename)

    current_app.logger.debug('SiteMapPage dispatch_request get for site: %s finished in %f seconds' % (sitename, time.time() - start_time))

    return rendered_template



class SitesDataAPI(BaseAPI):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.station = None
    self.site_type = None
    self.return_wq_limits = False
    self.return_project_area = False

    #If provided, this is a specific site to look up.
    if 'site' in request.args:
      self.station = request.args['site']
    #If provided, this will return only sites that match this type.
    if 'site_type' in request.args:
      self.site_type = request.args['site_type']
    #If provided, this will provide the bacteria test limits for water quality.
    if 'wq_limits' in request.args:
      self.return_wq_limits = bool(request.args['wq_limits'])
    #If provided, will return info about the project area, such as the name.
    if 'project_area' in request.args:
      self.return_project_area = bool(request.args['project_area'])

    return
  def load_data_file(self, filename):
    current_app.logger.debug("load_data_file Started.")

    try:
      current_app.logger.debug("Opening file: %s" % (filename))
      with open(filename, 'r') as data_file:
        return json.load(data_file)

    except (IOError, Exception) as e:
      current_app.logger.exception(e)
    return None

  def get_site_message(self, sitename):
    current_app.logger.debug('IP: %s get_site_message started' % (request.remote_addr))
    start_time = time.time()
    try:
      rec = db.session.query(Site_Message)\
        .join(Project_Area, Project_Area.id == Site_Message.site_id)\
        .filter(Project_Area.area_name == sitename).first()
    except Exception as e:
      current_app.logger.exception(e)
    current_app.logger.debug('get_site_message finished in %f seconds' % (time.time()-start_time))
    return rec

  def get_advisory_limits(self, sitename):
    current_app.logger.debug('get_advisory_limits started')
    start_time = time.time()
    try:
      #Get the advisroy limits
      limit_recs = db.session.query(Advisory_Limits)\
        .join(Project_Area, Project_Area.id == Advisory_Limits.site_id)\
        .filter(Project_Area.area_name == sitename)\
        .order_by(Advisory_Limits.min_limit).all()
      limits = {}
      for limit in limit_recs:
        limits[limit.limit_type] = {
          'min_limit': limit.min_limit,
          'max_limit': limit.max_limit
        }
    except Exception as e:
      current_app.logger.exception(e)
    current_app.logger.debug('get_advisory_limits finished in %f seconds' % (time.time()-start_time))
    return limits

  def create_shellfish_properties(self, shellfish_data, site_rec, data_timeout):
    try:
      region, site_name = site_rec.site_name.split('-')
      if region in shellfish_data:
        closure_data = shellfish_data[region]
        advisory = False
        if closure_data['Storm_Closure'].lower() == 'closed':
          advisory = True
        properties = {
          'station': site_name,
          'region': region,
          'advisory': {
            'date': closure_data['date_time_last_check'],
            'value': advisory,
            'hours_data_valid': data_timeout
          }
        }
        return properties
    except Exception as e:
      current_app.logger.exception(e)
    return None

  def create_camera_properties(self, site_rec):
    try:
        properties = {
          'station': site_rec.site_name
        }
        return properties
    except Exception as e:
      current_app.logger.exception(e)
    return None

  def create_rip_current_properties(self, sitename, ripcurrents_data, site_rec, data_timeout):
    try:
      #For the time being handle follybeach different than sarasota.
      if sitename == 'follybeach':
        if sitename in ripcurrents_data:
          #features = ripcurrents_data['features']
          #ndx = locate_element(features, lambda data: data['properties']['description'] == site_rec.site_name)
          forecasts = ripcurrents_data[sitename]
          properties = {
            'station': site_rec.site_name,
            'advisory': {
              'date': forecasts['date'],
              'value': forecasts['riprisk'].upper(),
              'flag': forecasts['riprisk'].upper(),
              'wfo_url':  forecasts['wfo_url'],
              'guidance_url': forecasts['guidance_url'],
              'description': site_rec.description,
              'hours_data_valid': data_timeout
              }
          }
      #For sarasota the rip current "stations" are used as the key into the nws file.
      elif sitename == 'sarasota':
        if site_rec.site_name.lower() in ripcurrents_data:
          forecasts = ripcurrents_data[site_rec.site_name.lower()]
          properties = {
            'station': site_rec.site_name,
            'advisory': {
              'date': forecasts['date'],
              'value': forecasts['riprisk'].upper(),
              'flag': forecasts['riprisk'].upper(),
              'wfo_url':  forecasts['wfo_url'],
              'guidance_url': forecasts['guidance_url'],
              'description': site_rec.description,
              'hours_data_valid': data_timeout
              }
          }

      return properties
    except Exception as e:
      current_app.logger.exception(e)
    return None

  def add_shellfish_data(self, sitename):
    shellfish_data = None
    if 'shellfish_closures' in SITES_CONFIG[sitename]:
      shellfish_data = self.load_data_file(SITES_CONFIG[sitename]['shellfish_closures'])

    return shellfish_data

  def get_sample_sites(self, sitename, **kwargs):
    try:
      station = kwargs.get('station', None)
      site_types = kwargs.get('site_types', None)
      sample_sites_query = db.session.query(Sample_Site) \
        .join(Project_Area, Project_Area.id == Sample_Site.project_site_id) \
        .join(Site_Type, Site_Type.id == Sample_Site.site_type_id) \
        .filter(Project_Area.area_name == sitename)
      if station is not None:
        sample_sites_query = sample_sites_query.filter(Sample_Site.site_name == station)
      elif site_types is not None:
        sample_sites_query = sample_sites_query.filter(Site_Type.name == site_types)

      sample_sites = sample_sites_query.all()
      return sample_sites
    except Exception as e:
      current_app.logger.error("IP: %s error getting samples sites from database." % (request.remote_addr))
      current_app.logger.exception(e)
    return None

  def get_bcrs_site_properties(self, siteid):
    properties = None
    try:
      bcrs_site = db.session.query(BeachAmbassador)\
      .filter(BeachAmbassador.sample_site_id == siteid)\
      .one()
      properties = {
        'bcrs_id': bcrs_site.bcrs_id,
        'site_url': bcrs_site.site_url
      }
    except Exception as e:
      current_app.logger.exception(e)
    return properties
  def get(self, sitename):
    start_time = time.time()
    current_app.logger.debug('IP: %s SiteDataAPI get for site: %s request args: %s' % (request.remote_addr, sitename, str(request.args)))
    ret_code = 501
    results =  {
      'sites': {},
    }
    if self.return_wq_limits:
      results['advisory_info'] =  {}
    if self.return_project_area:
      results['project_area'] = {}

    try:
      if sitename in SITES_CONFIG:
        ret_code = 200
        prediction_data = self.load_data_file(SITES_CONFIG[sitename]['prediction_file'])
        advisory_data = self.load_data_file(SITES_CONFIG[sitename]['advisory_file'])

        #Does site have shellfish data?
        shellfish_data = self.add_shellfish_data(sitename)

        #Does site have ripcurrents data?
        ripcurrents_data = None
        if 'ripcurrents' in SITES_CONFIG[sitename]:
          ripcurrents_data = self.load_data_file(SITES_CONFIG[sitename]['ripcurrents'])

        sample_sites = self.get_sample_sites(sitename, station=self.station, site_types=self.site_type)

        if self.return_wq_limits:
          limits = self.get_advisory_limits(sitename)
          if limits is not None:
            results['advisory_info']['limits'] = limits

        features = []

        for ndx,site_rec in enumerate(sample_sites):
          #We set the project info once.
          if self.return_project_area and ndx == 0:
            results['project_area'] = {
              'name': site_rec.project_site.display_name
            }
          if site_rec.site_type.name is not None:
            site_type = site_rec.site_type.name
          else:
            site_type = 'Water Quality'
          #All sites will have some base properties.
          properties = {
            'description': site_rec.description,
            'site_type': site_type,
            'site_name': site_rec.site_name,
            'city': site_rec.city,
            'post_code': site_rec.post_code,
            'state_code': site_rec.state_abbreviation,
            'county': site_rec.county
            }
          #Default sites are water quality sites, so we will check the predicition and advisory data and add to our response.
          if site_type == 'Water Quality':
            properties[site_type] = {'issues_advisories': site_rec.issues_advisories,
                                      'under_advisory': site_rec.has_current_advisory,
                                      'current_advisory_text': site_rec.advisory_text
                                    }

            if prediction_data is not None:
              prediction_sites = prediction_data['contents']['stationData']['features']
              #Find if the site has a prediction
              ndx = locate_element(prediction_sites, lambda wq_site: wq_site['properties']['station'] == site_rec.site_name)
              if ndx != -1:
                try:
                  data_timeout = SITE_TYPE_DATA_VALID_TIMEOUTS['Nowcast']
                  if type(prediction_data['contents']['run_date']) is not list:
                    run_date = prediction_data['contents']['run_date']
                  else:
                    run_date = prediction_data['contents']['run_date'][0]
                  properties[site_type]['nowcasts'] = {'date': run_date,
                                                       'level': prediction_sites[ndx]['properties']['ensemble'],
                                                       'hours_data_valid': data_timeout
                                                       }
                except Exception as e:
                  current_app.logger.exception(e)
            if advisory_data is not None:
              advisory_sites = advisory_data['features']
              #Find if the site has advisory data
              ndx = locate_element(advisory_sites, lambda wq_site: wq_site['properties']['station'] == site_rec.site_name)
              if ndx != -1:
                try:
                  if len(advisory_sites[ndx]['properties']['test']['beachadvisories']):
                    data_timeout = SITE_TYPE_DATA_VALID_TIMEOUTS[site_type]
                    properties[site_type]['advisory'] = {'date': advisory_sites[ndx]['properties']['test']['beachadvisories']['date'],
                                                         'value': advisory_sites[ndx]['properties']['test']['beachadvisories']['value'],
                                                         'hours_data_valid': data_timeout}
                except Exception as e:
                  current_app.logger.exception(e)

          elif site_type == 'Shellfish' and shellfish_data is not None:
            data_timeout = SITE_TYPE_DATA_VALID_TIMEOUTS[site_type]
            property = self.create_shellfish_properties(shellfish_data, site_rec, data_timeout)
            if property is not None:
              properties[site_type] = property

          elif site_type == 'Rip Current' and ripcurrents_data is not None:
            data_timeout = SITE_TYPE_DATA_VALID_TIMEOUTS[site_type]
            property = self.create_rip_current_properties(sitename, ripcurrents_data, site_rec, data_timeout)
            if property is not None:
              properties[site_type] = property
          elif site_type == 'Camera Site':
            property = self.create_camera_properties(site_rec)
            if property is not None:
              properties[site_type] = property
          elif site_type == 'Beach Ambassador':
            property = self.get_bcrs_site_properties(site_rec.id)
            if property is not None:
              properties[site_type] = property

          feature = geojson.Feature(id=site_rec.site_name,
                                    geometry=geojson.Point((site_rec.longitude,site_rec.latitude)),
                                    properties=properties)
          features.append(feature)
        results['sites'] = geojson.FeatureCollection(features)
        client_results = json.dumps(results)
        current_app.logger.debug("IP: %s SiteDataAPI processed %d features" % (request.remote_addr, len(features)))
      else:
        sites = list(SITES_CONFIG.keys())

        #results = build_json_error(400, "Site: %s is not a vaild site. Valid sites: %s" % (sitename,sites))
        results = self.json_error_response(400, "Site: %s is not a vaild site. Valid sites: %s" % (sitename,sites))
        client_results = json.dumps(results)

    except Exception as e:
      current_app.logger.exception(e)
      #client_results = build_json_error(501, 'Server encountered a problem with the query.')
      client_results = self.json_error_response(501, 'Server encountered a problem with the query.')

    current_app.logger.debug('IP: %s SiteDataAPI get for site: %s finished in %f seconds' % (request.remote_addr,
                                                                                             sitename,
                                                                                             time.time() - start_time))

    return (client_results, ret_code, {'Content-Type': 'application/json'})

class SiteBacteriaDataAPI(MethodView):
  def load_data_file(self, filename):
    current_app.logger.debug("load_data_file Started.")

    try:
      current_app.logger.debug("Opening file: %s" % (filename))
      with open(filename, 'r') as data_file:
        return json.load(data_file)

    except (IOError, Exception) as e:
      current_app.logger.exception(e)
    return None

  def get_requested_station_data(self, station, start_date_obj, end_date_obj, station_directory):
    start_time = time.time()
    current_app.logger.debug("get_requested_station_data Station: %s Start Date: %s End Date: %s"\
                             % (station, start_date_obj, end_date_obj))

    results = []
    try:
      filepath = os.path.join(station_directory, '%s.json' % (station))
      current_app.logger.debug("Opening station file: %s" % (filepath))

      with open(filepath, "r") as json_data_file:
        stationJson = geojson.load(json_data_file)

        advisoryList = stationJson['properties']['test']['beachadvisories']
        for ndx in range(len(advisoryList)):
          #Handle a bunch of different possibilites for the date format. In the future
          #hopefully we move to a standard.
          try:
            tst_date_obj = datetime.strptime(advisoryList[ndx]['date'], "%Y-%m-%d")
          except ValueError as e:
            try:
              tst_date_obj = datetime.strptime(advisoryList[ndx]['date'], "%Y-%m-%d %H:%M:%S")
            except ValueError as e:
              try:
                tst_date_obj = datetime.strptime(advisoryList[ndx]['date'], "%Y-%m-%dT%H:%M:%SZ")
              except ValueError as e:
                current_app.logger.exception(e)
                tst_date_obj = None

          if tst_date_obj is not None and (tst_date_obj >= start_date_obj and tst_date_obj < end_date_obj):
            result = advisoryList[ndx]
            value = result['value']
            try:
              value = float(value)
            except (Exception, ValueError) as e:
              value = result['value']
              current_app.logger.error("Converting value to float: %s (%s) had a problem, attemping cleaning."\
                                       % (value, type(value)))
              if type(value) is list:
                current_app.logger.error("Value is a list, getting first element")
                value = value[0]
              try:
                value = float(value)
              except (Exception, ValueError) as e:
                current_app.logger.error("Converting value to float: %s had a problem" % (value))
                value = 10
            results.append({'date': tst_date_obj.strftime('%Y-%m-%d %H:%M:%S'),
                            'value': value})

      return results
    except (IOError, ValueError, Exception) as e:
      current_app.logger.exception(e)

    return None
  def get(self, sitename=None, site=None):
    start_time = time.time()
    current_app.logger.debug('IP: %s SiteBacteriaDataAPI get for %s site: %s' % (request.remote_addr, sitename, site))
    ret_code = 404
    results = {}

    try:
      if sitename in SITES_CONFIG:
        start_date_obj = None
        end_date_obj = None
        if 'startdate' in request.args:
          start_date = request.args['startdate']
          start_date_obj = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        else:
          current_app.logger.error('IP: %s SiteBacteriaDataAPI ERROR get for %s site: %s startdate not supplied' % (request.remote_addr, sitename, site))
          results = build_json_error(404, "startdate parameter must be included in POST.")
        if 'enddate' in request.args:
          end_date = request.args['enddate']
          end_date_obj = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
        else:
          current_app.logger.error('IP: %s SiteBacteriaDataAPI ERROR get for %s site: %s enddate not supplied' % (request.remote_addr, sitename, site))
          results = build_json_error(404, "enddate parameter must be included in POST.")
        if start_date_obj is not None and end_date_obj is not None:
          try:
            site_rec = db.session.query(Sample_Site) \
              .join(Project_Area, Project_Area.id == Sample_Site.project_site_id) \
              .join(Site_Type, Site_Type.id == Sample_Site.site_type_id) \
              .filter(Sample_Site.site_name == site)\
              .filter(Project_Area.area_name == sitename).one()
          except exc.SQLAlchemyError as e:
            ret_code = 404
            results = build_json_error(404, 'Site: %s does not exist.' % (site))
          except Exception as e:
            current_app.logger.exception(e)
            ret_code = 501
            results = build_json_error(501, 'Server encountered a problem with the query.' % (site))
          else:
            if site_rec.site_type.name is not None:
              site_type = site_rec.site_type.name
            else:
              site_type = 'Water Quality'
            # All sites will have some base properties.
            properties = {'description': site_rec.description,
                          'site_type': site_type,
                          'site_name': site_rec.site_name
                          }

            ret_code = 200

            properties[site_type] = {'advisory': {'results': []}}

            prediction_data = self.load_data_file(SITES_CONFIG[sitename]['prediction_file'])
            if prediction_data is not None:
              prediction_sites = prediction_data['contents']['stationData']['features']
              #Find if the site has a prediction
              ndx = locate_element(prediction_sites, lambda wq_site: wq_site['properties']['station'] == site)
              if ndx != -1:
                try:
                  data_timeout = SITE_TYPE_DATA_VALID_TIMEOUTS['Nowcast']
                  properties[site_type]['nowcasts'] = {'date': prediction_data['contents']['run_date'],
                                                       'level': prediction_sites[ndx]['properties']['ensemble'],
                                                       'hours_data_valid': data_timeout
                                                       }
                except Exception as e:
                  current_app.logger.exception(e)


            site_data = self.get_requested_station_data(site,
                                                        start_date_obj,
                                                        end_date_obj,
                                                        SITES_CONFIG[sitename]['stations_directory'])
            if site_data is not None:
              data_timeout = SITE_TYPE_DATA_VALID_TIMEOUTS[site_type]
              properties[site_type]['advisory'] = {
                'results': site_data,
                'hours_data_valid': data_timeout}

              #properties[site_type]['advisory']['results'] = site_data
            results = geojson.Feature(id=site_rec.site_name,
                                      geometry=geojson.Point((site_rec.longitude, site_rec.latitude)),
                                      properties=properties)

      else:
        results = build_json_error(404, 'Site: %s not found' % (sitename))

      results = geojson.dumps(results)
    except Exception as e:
      current_app.logger.exception(e)
      results = build_json_error(501, 'Server experienced a procesing error')

    current_app.logger.debug('SiteBacteriaDataAPI get for site: %s finished in %f seconds' % (sitename, time.time() - start_time))
    return (results, ret_code, {'Content-Type': 'application/json'})

class CollectionProgramInfoAPI(BaseAPI):
  def build_json(self, recs):
    result = {
      'type': 'Feature',
      'geometry': {

      },
      'properties': {
        'program': {}
      }
    }
    for rec in recs:
        program = result['properties']['program']
        program_name = rec.program_type.program_type
        program[program_name] = \
        {
          'program_name': rec.program,
          'description': rec.description,
          'url': rec.url,
          'program_type': rec.program_type.program_type,
          'state': rec.state
        }
    return result
  def get(self, sitename=None):
    start_time = time.time()
    current_app.logger.debug('IP: %s WaterQualityProgramAPI get for %s.' % (request.remote_addr, sitename))
    ret_code = 404
    results = {}
    try:
      program_info = db.session.query(Collection_Program_Info) \
        .join(Collection_Program_Info_Mapper, Collection_Program_Info_Mapper.collection_program_info_id == Collection_Program_Info.id) \
        .join(Project_Area, Project_Area.id == Collection_Program_Info_Mapper.project_area_id) \
        .filter(Project_Area.area_name == sitename)

      if 'program_type' in request.args:
        program_type = request.args['program_type']
        program_info = program_info.join(Collection_Program_Type, Collection_Program_Type.id == Collection_Program_Info.program_type_id) \
          .filter(Collection_Program_Type.program_type == program_type)


      program_info_recs = program_info.all()
      results = self.build_json(program_info_recs)
      ret_code = 200
    except Exception as e:
      results = self.json_error_response(501, "Error querying Water Quality Program info.")
      current_app.logger.exception(e)

    return (results, ret_code, {'Content-Type': 'application/json'})

class EPAUVIndex(BaseAPI):
  """
  This is our proxy to the EPA Rest request. The EPA site did not seem to allow CORS so our request kept
  getting denied.
  """
  def get(self, sitename=None):
    start_time = time.time()
    current_app.logger.debug('IP: %s WaterQualityProgramAPI get for %s.' % (request.remote_addr, sitename))
    ret_code = 404
    results = {}
    try:
      url = None
      if 'post_code' in request.args:
        url = "https://enviro.epa.gov/enviro/efservice/getEnvirofactsUVHOURLY/ZIP/{post_code}/json".format(post_code=request.args['post_code'])
      if url:
        current_app.logger.debug("IP: %s EPAUVIndex querying: %s" % (request.remote_addr, url))
        req = requests.get(url)
        if req.status_code == 200:
          results = req.text
          ret_code = 200
        else:
          results = self.json_error_response(req.status_code, req.text)
          ret_code = 404
    except Exception as e:
      results = self.json_error_response(501, "Error querying the EPA IV Index data.")
      current_app.logger.exception(e)

    return (results, ret_code, {'Content-Type': 'application/json'})

class BCRSQuery(BaseAPI):
  def get(self, sitename=None):
    start_time = time.time()
    current_app.logger.debug('IP: %s WaterQualityProgramAPI get for %s.' % (request.remote_addr, sitename))
    ret_code = 404
    results = {}
    try:
      #url = 'https://api.visitbeaches.org/graphql?"{"operationName":"GetMappedReports","variables":{"layerId":"2","bounds":{"northEast":{"latitude":36.14066444947063,"longitude":-75.61921185747138},"southWest":{"latitude":20.140664449470627,"longitude":-91.61921185747138}}},"query":"query GetMappedReports($bounds: BoundsInput!, $layerId: ID!) {\n  beaches(orderBy: [{column: NAME, order: ASC}]) {\n    ...Beach\n    __typename\n  }\n  clusteredLayerReports(layerId: $layerId, bounds: $bounds) {\n    clusters {\n      ...Cluster\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment Beach on Beach {\n  id\n  name\n  website\n  logo\n  latitude\n  longitude\n  amenities {\n    description\n    link\n    __typename\n  }\n  imageAttachments(orderBy: [{column: CREATED_AT, order: DESC}]) {\n    ...ImageAttachment\n    __typename\n  }\n  city {\n    ...City\n    __typename\n  }\n  location\n  __typename\n}\n\nfragment City on City {\n  name\n  latitude\n  longitude\n  county {\n    ...County\n    __typename\n  }\n  state {\n    ...State\n    __typename\n  }\n  __typename\n}\n\nfragment County on County {\n  name\n  latitude\n  longitude\n  state {\n    ...State\n    __typename\n  }\n  __typename\n}\n\nfragment State on State {\n  name\n  abbreviation\n  latitude\n  longitude\n  __typename\n}\n\nfragment ImageAttachment on ImageAttachment {\n  originalUrl\n  previewUrl\n  thumbnailUrl\n  __typename\n}\n\nfragment Cluster on Cluster {\n  key\n  center {\n    latitude\n    longitude\n    __typename\n  }\n  reports {\n    ...Report\n    __typename\n  }\n  __typename\n}\n\nfragment Report on Report {\n  id\n  user {\n    ...User\n    __typename\n  }\n  agree\n  disagree\n  createdAt\n  latitude\n  longitude\n  reportParameters {\n    ...ReportParameter\n    __typename\n  }\n  reportableType\n  reportableId\n  __typename\n}\n\nfragment ReportParameter on ReportParameter {\n  parameter {\n    ...Parameter\n    __typename\n  }\n  parameterValues {\n    ...ParameterValue\n    __typename\n  }\n  value\n  display\n  __typename\n}\n\nfragment Parameter on Parameter {\n  id\n  name\n  icon\n  prompt\n  description\n  type\n  rangeMin\n  rangeMax\n  unit\n  first\n  parameterCategory {\n    ...ParameterCategory\n    __typename\n  }\n  parameterValues {\n    ...ParameterValue\n    __typename\n  }\n  __typename\n}\n\nfragment ParameterCategory on ParameterCategory {\n  id\n  name\n  icon\n  description\n  slug\n  order\n  __typename\n}\n\nfragment ParameterValue on ParameterValue {\n  id\n  name\n  description\n  value\n  imagePath\n  icon\n  __typename\n}\n\nfragment User on User {\n  id\n  name\n  email\n  alert {\n    ...Alert\n    __typename\n  }\n  __typename\n}\n\nfragment Alert on Alert {\n  id\n  uuid\n  email\n  beaches {\n    ...Beach\n    __typename\n  }\n  __typename\n}\n"}"'

      url = "https://api.visitbeaches.org/graphql"
      params = {
        'operationName': 'GetMappedReports',
        'variables': {
             "bounds": {
               "northEast": {
                 "latitude": 27.547242,
                 "longitude": -82.524490
               },
               "southWest": {
                 "latitude": 27.255850,
                 "longitude": -82.814941
               }
             },
             "layerId": "2"
           },
        "query": """query GetMappedReports($bounds: BoundsInput!, $layerId: ID!) {\n  beaches(orderBy: [{column: NAME, order: ASC}]) {\n    ...Beach\n    __typename\n  }\n  clusteredLayerReports(layerId: $layerId, bounds: $bounds) {\n    clusters {\n      ...Cluster\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment Beach on Beach {\n  id\n  name\n  website\n  logo\n  latitude\n  longitude\n  amenities {\n    description\n    link\n    __typename\n  }\n  imageAttachments(orderBy: [{column: CREATED_AT, order: DESC}]) {\n    ...ImageAttachment\n    __typename\n  }\n  city {\n    ...City\n    __typename\n  }\n  location\n  __typename\n}\n\nfragment City on City {\n  name\n  latitude\n  longitude\n  county {\n    ...County\n    __typename\n  }\n  state {\n    ...State\n    __typename\n  }\n  __typename\n}\n\nfragment County on County {\n  name\n  latitude\n  longitude\n  state {\n    ...State\n    __typename\n  }\n  __typename\n}\n\nfragment State on State {\n  name\n  abbreviation\n  latitude\n  longitude\n  __typename\n}\n\nfragment ImageAttachment on ImageAttachment {\n  originalUrl\n  previewUrl\n  thumbnailUrl\n  __typename\n}\n\nfragment Cluster on Cluster {\n  key\n  center {\n    latitude\n    longitude\n    __typename\n  }\n  reports {\n    ...Report\n    __typename\n  }\n  __typename\n}\n\nfragment Report on Report {\n  id\n  user {\n    ...User\n    __typename\n  }\n  agree\n  disagree\n  createdAt\n  latitude\n  longitude\n  reportParameters {\n    ...ReportParameter\n    __typename\n  }\n  reportableType\n  reportableId\n  __typename\n}\n\nfragment ReportParameter on ReportParameter {\n  parameter {\n    ...Parameter\n    __typename\n  }\n  parameterValues {\n    ...ParameterValue\n    __typename\n  }\n  value\n  display\n  __typename\n}\n\nfragment Parameter on Parameter {\n  id\n  name\n  icon\n  prompt\n  description\n  type\n  rangeMin\n  rangeMax\n  unit\n  first\n  parameterCategory {\n    ...ParameterCategory\n    __typename\n  }\n  parameterValues {\n    ...ParameterValue\n    __typename\n  }\n  __typename\n}\n\nfragment ParameterCategory on ParameterCategory {\n  id\n  name\n  icon\n  description\n  slug\n  order\n  __typename\n}\n\nfragment ParameterValue on ParameterValue {\n  id\n  name\n  description\n  value\n  imagePath\n  icon\n  __typename\n}\n\nfragment User on User {\n  id\n  name\n  email\n  alert {\n    ...Alert\n    __typename\n  }\n  __typename\n}\n\nfragment Alert on Alert {\n  id\n  uuid\n  email\n  beaches {\n    ...Beach\n    __typename\n  }\n  __typename\n}\n"""
      }

      if url:
        #current_app.logger.debug("IP: %s BCRSQuery querying: %s" % (request.remote_addr, url))
        req = requests.post(url, json=params)
        current_app.logger.debug("IP: %s BCRSQuery querying URL: %s Headers: %s" % (request.remote_addr, req.url, req.headers))
        if req.status_code == 200:
          results = req.text
          ret_code = 200
        else:
          results = self.json_error_response(req.status_code, req.text)
          ret_code = 404
    except Exception as e:
      results = self.json_error_response(501, "Error querying the EPA IV Index data.")
      current_app.logger.exception(e)

    return (results, ret_code, {'Content-Type': 'application/json'})


def build_json_error(error_code, error_message):
  json_error = {}
  json_error['error'] = {'message': error_message}
  return json_error