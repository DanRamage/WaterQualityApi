import os
from flask import request, redirect, render_template, current_app, url_for
from flask.views import View, MethodView
import flask_admin as admin
import flask_login as login
from flask_admin.contrib import sqla
from flask_admin import helpers, expose
from flask_security import current_user
import pandas as pd
import geopandas as gpd
import requests
import time
import json
import geojson
from datetime import datetime, timedelta
import pytz
import dateparser
from wtforms import form, fields, validators
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import exc
from sqlalchemy.ext.declarative import DeclarativeMeta
from shapely.wkb import loads as wkb_loads
from shapely.wkt import loads as wkt_loads
from shapely import from_wkt, to_geojson, get_coordinates
from json_timeseries import TsRecord, TimeSeries, JtsDocument

from config import VALID_UPDATE_ADDRESSES, SITES_CONFIG, SITE_TYPE_DATA_VALID_TIMEOUTS

from app import db
from .admin_models import User
from .wq_models import Project_Area, \
  Site_Message, \
  Advisory_Limits, \
  Sample_Site, \
  Sample_Site_Data, \
  Site_Type, \
  Collection_Program_Info, \
  Collection_Program_Info_Mapper, \
  Collection_Program_Type, \
  BeachAmbassador, \
  WebCoos, \
  usgs_sites, \
  ShellCast, \
  BeachAccess, \
  GeneralProgramPopup,\
  DataTimeouts


def locate_element(list, filter):
  for ndx, x in enumerate(list):
    if filter(x):
      return ndx
  return -1


def BBOXtoPolygon(bbox):
  try:
    bounding_box = request.args['bbox'].split(',')
    if len(bounding_box) == 4:
      wkt_query_polygon = 'POLYGON(({x1} {y1}, {x1} {y2}, {x2} {y2}, {x2} {y1}, {x1} {y1}))'.format(
        x1=bounding_box[0],
        y1=bounding_box[1],
        x2=bounding_box[2],
        y2=bounding_box[3]
      )
      query_polygon = wkt_loads(wkt_query_polygon)
      return query_polygon
  except Exception as e:
    current_app.logger.exception(e)
  return None


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

class SitePage(View):
  def __init__(self, site_name):
    current_app.logger.debug('__init__')
    self.site_name = site_name
    self.page_template = 'index_template.html'
    self._data_types = {}

  def get_area_message(self):
    current_app.logger.debug('IP: %s get_area_message started' % (request.remote_addr))
    start_time = time.time()
    rec = db.session.query(Site_Message)\
      .join(Project_Area, Project_Area.id == Site_Message.site_id)\
      .filter(Project_Area.area_name == self.site_name).first()
    current_app.logger.debug('get_area_message finished in %f seconds' % (time.time()-start_time))
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

'''
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
'''
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
from flask_admin.contrib.sqla.filters import BooleanEqualFilter
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
  column_list = ['id', 'project_site', 'site_name', 'site_type', 'latitude', 'longitude', 'description', 'epa_id', 'city', 'county', 'post_code', 'state_abbreviation', 'issues_advisories', 'has_current_advisory', 'advisory_text', 'boundaries', 'temporary_site', 'site_data', 'row_entry_date', 'row_update_date']
  form_columns = ['project_site', 'site_name', 'site_type', 'latitude', 'longitude', 'description', 'epa_id', 'city', 'county', 'post_code', 'state_abbreviation', 'site_data','issues_advisories', 'has_current_advisory', 'advisory_text', 'boundaries', 'temporary_site']
  column_filters = ['project_site', 'site_type', 'city']
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
    current_app.logger.debug('IP: %s User: %s sample_site_view on_model_change started.' % (request.remote_addr, current_user.login))

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

    current_app.logger.debug('IP: %s User: %s sample_site_view on_model_change finished in %f seconds.' % (request.remote_addr, current_user.login, time.time() - start_time))

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

class webcoos_sites(base_view):
  column_list = ['id', 'webcoos_id', 'sample_site_name', 'site_url', 'row_entry_date', 'row_update_date']
  form_columns = ['webcoos_id', 'sample_site_name', 'site_url', 'row_entry_date', 'row_update_date']
  column_filters = ['webcoos_id', 'sample_site_name', 'site_url', 'row_entry_date', 'row_update_date']

class usgs_sites_view(base_view):
  column_list = ['id', 'sample_site_name', 'usgs_site_id', 'parameters_to_query', 'row_entry_date', 'row_update_date']
  form_columns = ['sample_site_name', 'usgs_site_id', 'parameters_to_query', 'row_entry_date', 'row_update_date']
  column_filters = ['sample_site_name', 'usgs_site_id']

class data_timeouts_view(base_view):
  column_list = ['id', 'name', 'hours_valid', 'project_site', 'site_type', 'row_entry_date', 'row_update_date']
  form_columns = ['name', 'hours_valid', 'project_site', 'site_type', 'row_entry_date', 'row_update_date']
  column_filters = ['project_site', 'site_type']

class shellcast_sites_view(base_view):
    column_list = ['id', 'site_id', 'sample_site_name', 'site_url', 'description', 'wkt_extent', 'row_entry_date', 'row_update_date']
    form_columns = ['site_id', 'sample_site_name', 'site_url', 'description', 'wkt_extent', 'row_entry_date', 'row_update_date']
    column_filters = ['site_id', 'sample_site_name', 'site_url', 'row_entry_date', 'row_update_date']

class general_popup_sites_view(base_view):
  column_list = ['id', 'sample_site_name',  'map_icon', 'header_title', 'icon', 'site_field', 'site_id',
                 'link_field', 'site_url', 'description','row_entry_date', 'row_update_date']
  form_columns = [ 'sample_site_name', 'map_icon', 'header_title', 'icon', 'site_field', 'site_id',
                 'link_field', 'site_url', 'description', 'row_entry_date', 'row_update_date']

  column_filters = ['site_id', 'sample_site_name', 'site_id', 'site_url', 'row_entry_date', 'row_update_date']


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

class HTBSitesAPI(BaseAPI):
  def get(self):
    start_time = time.time()
    current_app.logger.debug(f"IP: {request.remote_addr} HTBSitesAPI get request args: {str(request.args)}")
    bbox = None
    if 'bbox' in request.args:
      bbox = BBOXtoPolygon(request.args['bbox'])

    ret_code = 501
    results = {
      'sites': {},
    }
    try:
      features = []
      if bbox is not None:
        sample_sites_query = db.session.query(Sample_Site, Project_Area.area_name.label('project_area_name'),
                                              Site_Type.name.label('site_type_name')) \
          .join(Project_Area, Project_Area.id == Sample_Site.project_site_id) \
          .join(Site_Type, Site_Type.id == Sample_Site.site_type_id) \
          .filter(Site_Type.name == 'Water Quality') \
          .order_by(Project_Area.display_name)
        bbox_series = gpd.GeoSeries([bbox])
        bbox_df = gpd.GeoDataFrame({'geometry': bbox_series})
        with db.engine.begin() as conn:
          # We give pandas the sql statement to make the query and build the dataframe from the results.
          df = pd.read_sql(sample_sites_query.statement, conn)
        # Create the geopandas dataframe using the points_from_xy to build the geometry column.
        geo_df = gpd.GeoDataFrame(df,
                                  geometry=gpd.points_from_xy(x=df.longitude, y=df.latitude))
        # Taking the passed in bounding box, we do an intersection to get the stations we are interested in.
        sample_sites = gpd.overlay(geo_df, bbox_df, how="intersection", keep_geom_type=False)

      else:
        sample_sites_query = db.session.query(Sample_Site) \
          .join(Project_Area, Project_Area.id == Sample_Site.project_site_id) \
          .join(Site_Type, Site_Type.id == Sample_Site.site_type_id) \
          .filter(Site_Type.name == 'Water Quality') \
          .order_by(Project_Area.display_name)
        sample_sites = sample_sites_query.all()

      features = self.build_feature_collection(sample_sites)
      #Build up a JSON response
      results['sites'] = geojson.FeatureCollection(features)
      ret_code = 200
    except Exception as e:
      current_app.logger.error("IP: %s error getting samples sites from database." % (request.remote_addr))
      current_app.logger.exception(e)

    current_app.logger.debug(f"IP: {request.remote_addr} HTBSitesAPI get finished in {time.time() - start_time} seconds")
    client_results = json.dumps(results)

    return (client_results, ret_code, {'Content-Type': 'application/json'})

  def build_feature_collection(self, db_records):
    features = []
    #Figure out what kind of records we're iterating through. If we did a BBOX GET, then
    #the records are a dataframe. Otherwise they are SQLAlchemy objects.
    if type(db_records) == gpd.GeoDataFrame:
      # Build up a JSON response
      for index, row in db_records.iterrows():
        properties = {
          'description': row['description'],
          'site_name': row['site_name'],
          'site_type': row['site_type_name'],
          'project_area': row['project_area_name']
        }
        feature = geojson.Feature(id=row['site_name'],
                                  geometry=geojson.Point((row['longitude'], row['latitude'])),
                                  properties=properties)
        features.append(feature)
    else:
        for sample_site in db_records:
          properties = {
            'description': sample_site.description,
            'site_type': sample_site.site_type.name,
            'site_name': sample_site.site_name,
            'project_area': sample_site.project_site.area_name
          }

          feature = geojson.Feature(id=sample_site.site_name,
                                    geometry=geojson.Point((sample_site.longitude,sample_site.latitude)),
                                    properties=properties)
          features.append(feature)

    return(features)

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

  def get_area_message(self, sitename):
    current_app.logger.debug('IP: %s get_area_message started' % (request.remote_addr))
    start_time = time.time()
    try:
      rec = db.session.query(Site_Message)\
        .join(Project_Area, Project_Area.id == Site_Message.site_id)\
        .filter(Project_Area.area_name == sitename).first()
    except Exception as e:
      current_app.logger.exception(e)
    current_app.logger.debug('get_area_message finished in %f seconds' % (time.time()-start_time))
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

  def create_camera_properties(self, siteid):
      properties = None
      try:
        camera_site = db.session.query(WebCoos) \
          .filter(WebCoos.sample_site_id == siteid) \
          .one()
        properties = {
          'id': camera_site.webcoos_id,
          'site_url': camera_site.site_url
        }
      except Exception as e:
        current_app.logger.exception(e)
      return properties

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

  def get_shellcast_site_properties(self, siteid):
    properties = site_geometry =None
    try:
      site = db.session.query(ShellCast)\
      .filter(ShellCast.sample_site_id == siteid)\
      .one()
      properties = {
        'id': site.site_id,
        'site_url': site.site_url
      }
      site_poly = wkt_loads(site.wkt_extent)
      site_geometry = json.loads(to_geojson(site_poly))
    except Exception as e:
      current_app.logger.exception(e)
    return (properties, site_geometry)

  def get_usgs_sites(self, siteid):
    properties = None
    try:
      usgs_site_recs = db.session.query(usgs_sites)\
      .filter(usgs_sites.sample_site_id == siteid)\
      .all()
      for rec in usgs_site_recs:
        if properties is None:
          properties = {}
        if rec.usgs_site_id not in properties:
          properties[rec.usgs_site_id] = {}
        properties = {
          'site_id': rec.usgs_site_id,
          'parameters_to_query': rec.parameters_to_query
        }
    except Exception as e:
      current_app.logger.exception(e)
    return properties

  def get_beach_access_properties(self, siteid):
    properties = None
    try:
      beach_access = db.session.query(BeachAccess)\
      .filter(BeachAccess.sample_site_id == siteid)\
      .one()

      properties = beach_access.to_json()
    except Exception as e:
      current_app.logger.exception(e)
    return properties

  def get_data_expirations(self, sitename):
    try:
      timeouts = db.session.query(DataTimeouts)\
        .join(Project_Area, Project_Area.id == DataTimeouts.project_site_id) \
        .filter(Project_Area.area_name == sitename) \
        .all()
      return timeouts
    except Exception as e:
      current_app.logger.exception(e)
    return None

  def get_general_popup_properties(self, siteid):
    exclude_columns = ['id', 'row_entry_date', 'row_update_date', 'sample_site_id']
    try:
      general_popup_rec = db.session.query(GeneralProgramPopup)\
        .filter(GeneralProgramPopup.sample_site_id == siteid) \
        .one()
      properies = to_json(general_popup_rec, exclude_columns)
      return properies
    except Exception as e:
      current_app.logger.exception(e)
    return None

  def is_valid_project_area(self, project_area_name):
    try:
      project_area_rec = db.session.query(Project_Area)\
        .filter(Project_Area.area_name == project_area_name)\
        .one()
      return True
    except Exception as e:
      current_app.logger.exception(e)
    return False

  def get_project_areas(self):
    try:
      project_area_rec = db.session.query(Project_Area.area_name)\
        .all()
      sites = [site[0] for site in project_area_rec]
      return sites
    except Exception as e:
      current_app.logger.exception(e)
    return []

  def build_site_type_properties(self, location_name, site_rec):
    if site_rec.site_type.name is not None:
      site_type = site_rec.site_type.name
    else:
      site_type = 'Water Quality'

    # All sites will have some base properties.
    properties = {
      'description': site_rec.description,
      'site_type': site_type,
      'site_name': site_rec.site_name,
      'city': site_rec.city,
      'post_code': site_rec.post_code,
      'state_code': site_rec.state_abbreviation,
      'county': site_rec.county
    }
    # The default site_geometry is going to be the Point() defined in the Sample_Site table.
    # We may have different geometry, such as polygon for shellcast, so the site_geometry is then
    # changed.
    site_geometry = geojson.Point((site_rec.longitude, site_rec.latitude))

    if site_type == 'Water Quality':
      prediction_data = None
      advisory_data = None
      if location_name in SITES_CONFIG:
        prediction_data = self.load_data_file(SITES_CONFIG[location_name]['prediction_file'])
        advisory_data = self.load_data_file(SITES_CONFIG[location_name]['advisory_file'])

      properties[site_type] = {'issues_advisories': site_rec.issues_advisories,
                               'under_advisory': site_rec.has_current_advisory,
                               'current_advisory_text': site_rec.advisory_text
                               }
      if prediction_data is not None:
        prediction_sites = prediction_data['contents']['stationData']['features']
        # Find if the site has a prediction
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
        # Find if the site has advisory data
        ndx = locate_element(advisory_sites, lambda wq_site: wq_site['properties']['station'] == site_rec.site_name)
        if ndx != -1:
          try:
            if len(advisory_sites[ndx]['properties']['test']['beachadvisories']):
              data_timeout = SITE_TYPE_DATA_VALID_TIMEOUTS[site_type]
              properties[site_type]['advisory'] = {
                'date': advisory_sites[ndx]['properties']['test']['beachadvisories']['date'],
                'value': advisory_sites[ndx]['properties']['test']['beachadvisories']['value'],
                'hours_data_valid': data_timeout}
          except Exception as e:
            current_app.logger.exception(e)

    elif site_type == 'Shellfish':
      # Does site have shellfish data?
      shellfish_data = self.add_shellfish_data(location_name)
      if shellfish_data is not None:
        data_timeout = SITE_TYPE_DATA_VALID_TIMEOUTS[site_type]
        property = self.create_shellfish_properties(shellfish_data, site_rec, data_timeout)
        if property is not None:
          properties[site_type] = property

    elif site_type == 'Camera Site':
      property = self.create_camera_properties(site_rec.id)
      if property is not None:
        properties[site_type] = property

    elif site_type == 'Beach Ambassador':
      property = self.get_bcrs_site_properties(site_rec.id)
      if property is not None:
        properties[site_type] = property

    elif site_type == 'Shellcast':
      property, site_geometry = self.get_shellcast_site_properties(site_rec.id)
      if property is not None:
        properties[site_type] = property

    elif site_type == "Beach Access":
      property = self.get_beach_access_properties(site_rec.id)
      if property is not None:
        properties[site_type] = property

    elif site_type == "Gills Creek Water Quality":

      properties[site_type] = {}
      site_data_filename = os.path.join(SITES_CONFIG[location_name]['stations_directory'], f"{site_rec.site_name}.json")
      json_data = self.load_data_file(site_data_filename)
      if json_data is not None:
        latest_date = json_data['properties']['header']['endTime']
        data_recs = json_data['properties']['data']
        latest_data = next((item for item in data_recs if item["ts"] == latest_date), None)
        latest_record = json_data['properties']
        latest_record['header']['startTime'] = latest_record['header']['endTime'] = latest_data['ts']
        latest_record['header']['recordCount'] = 1
        #Now replace the data with the latest record, getting rid of the rest.
        latest_record['data'] = [latest_data]
        properties[site_type] = {'timeseries': latest_record}

    elif site_type == "General Popup Site":
      property = self.get_general_popup_properties(site_rec.id)
      if property is not None:
        properties[site_type] = property

    extents_json = None
    if len(site_rec.extents):
      properties['extents_geometry'] = []
      for extent in site_rec.extents:
        extent_feature = geojson.Feature(id=f"{extent.extent_name}_{extent.id}_extent",
                                         geometry=from_wkt(extent.wkt_extent),
                                         properties={'extent_name': extent.extent_name})
        properties['extents_geometry'].append(extent_feature)

    # Check to see if the site will be adding any USGS obs onto the station page.
    usgs_properties = self.get_usgs_sites(site_rec.id)
    if usgs_properties is not None:
      if 'site_observations' not in properties:
        properties['site_observations'] = {}
      properties['site_observations']['usgs_sites'] = usgs_properties

    return properties, site_geometry

  def get(self, sitename):
    start_time = time.time()
    current_app.logger.debug('IP: %s SiteDataAPI get for site: %s request args: %s' % (request.remote_addr, sitename, str(request.args)))
    ret_code = 501
    results = {
      'sites': {},
    }
    if self.return_wq_limits:
      results['advisory_info'] =  {}
    if self.return_project_area:
      results['project_area'] = {}

    try:
      if self.is_valid_project_area(sitename):
        ret_code = 200
        sample_sites = self.get_sample_sites(sitename, station=self.station, site_types=self.site_type)
        data_expirations = self.get_data_expirations(sitename)
        if self.return_wq_limits:
          limits = self.get_advisory_limits(sitename)
          if limits is not None:
            results['advisory_info']['limits'] = limits

        area_message = self.get_area_message(sitename)
        features = []

        for ndx,site_rec in enumerate(sample_sites):
          #We set the project info once.
          if self.return_project_area and ndx == 0:
            results['project_area'] = {
              'name': site_rec.project_site.display_name,
              'message': ''
            }
            if area_message is not None:
              results['project_area']['message'] = area_message.message

          properties, site_geometry = self.build_site_type_properties(sitename, site_rec)
          '''
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

          elif site_type == 'Camera Site':
            property = self.create_camera_properties(site_rec.id)
            if property is not None:
              properties[site_type] = property

          elif site_type == 'Beach Ambassador':
            property = self.get_bcrs_site_properties(site_rec.id)
            if property is not None:
              properties[site_type] = property

          elif site_type == 'Shellcast':
            property, site_geometry = self.get_shellcast_site_properties(site_rec.id)
            if property is not None:
              properties[site_type] = property
          elif site_type == "Beach Access":
            property = self.get_beach_access_properties(site_rec.id)
            if property is not None:
              properties[site_type] = property
          extents_json = None
          if len(site_rec.extents):
            properties['extents_geometry'] = []
            for extent in site_rec.extents:
              extent_feature = geojson.Feature(id=f"{extent.extent_name}_{extent.id}_extent",
                                              geometry=from_wkt(extent.wkt_extent),
                                               properties={'extent_name': extent.extent_name})
              properties['extents_geometry'].append(extent_feature)

          #Check to see if the site will be adding any USGS obs onto the station page.
          usgs_properties = self.get_usgs_sites(site_rec.id)
          if usgs_properties is not None:
            if 'site_observations' not in properties:
              properties['site_observations'] = {}
            properties['site_observations']['usgs_sites'] = usgs_properties
        '''
          feature = geojson.Feature(id=site_rec.site_name,
                                    geometry=site_geometry,
                                    properties=properties)
          features.append(feature)
        results['sites'] = geojson.FeatureCollection(features)
        client_results = json.dumps(results)
        current_app.logger.debug("IP: %s SiteDataAPI processed %d features" % (request.remote_addr, len(features)))
      else:
        sites = self.get_project_areas()
        results = self.json_error_response(400, "Site: %s is not a valid site. Valid sites: %s" % (sitename,sites))
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

  def is_valid_project_area(self, project_area_name):
    try:
      project_area_rec = db.session.query(Project_Area)\
        .filter(Project_Area.area_name == project_area_name)\
        .one()
      return True
    except Exception as e:
      current_app.logger.exception(e)
    return False

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

          if tst_date_obj is not None and (start_date_obj <= tst_date_obj < end_date_obj):
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
      if self.is_valid_project_area(sitename):
      #if sitename in SITES_CONFIG:
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
              .filter(Project_Area.area_name == sitename).all()
          except exc.SQLAlchemyError as e:
            ret_code = 404
            results = build_json_error(404, 'Site: %s does not exist.' % (site))
          except Exception as e:
            current_app.logger.exception(e)
            ret_code = 501
            results = build_json_error(501, 'Server encountered a problem with the query.' % (site))
          else:
            if len(site_rec) > 1:
              current_app.logger.error(f"Multiple records for site: {site} returned.")
            site_rec = site_rec[0]
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


class SiteDataAPI(MethodView):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.station = None
    self.site_type = None
    self.return_wq_limits = False
    self.return_project_area = False
    self.get_usgs_properties = False
    #If the endpoint is site_display_data, we'll return these pieces of information in the site properties.
    if request.endpoint == 'site_display_data':
      self.station = True
      self.return_wq_limits = True
      self.return_project_area = True
      self.get_usgs_properties = True
    '''
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
  '''
    self._start_date_obj = self._end_date_obj = None
    if 'startdate' in request.args:
      start_date = request.args['startdate']
      start_date_obj = dateparser.parse(start_date)
      self._start_date_obj = pytz.utc.localize(start_date_obj)

    if 'enddate' in request.args:
      end_date = request.args['enddate']
      end_date_obj = dateparser.parse(end_date)
      self._end_date_obj = pytz.utc.localize(end_date_obj)

    return

  def is_valid_project_area(self, project_area_name):
    try:
      db.session.query(Project_Area)\
        .filter(Project_Area.area_name == project_area_name)\
        .one()
      return True
    except Exception as e:
      current_app.logger.exception(e)
    return False

  def get_area_message(self, sitename):
    current_app.logger.debug('IP: %s get_area_message started' % (request.remote_addr))
    start_time = time.time()
    try:
      rec = db.session.query(Site_Message)\
        .join(Project_Area, Project_Area.id == Site_Message.site_id)\
        .filter(Project_Area.area_name == sitename).first()
    except Exception as e:
      current_app.logger.exception(e)
    current_app.logger.debug('get_area_message finished in %f seconds' % (time.time()-start_time))
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

  def get_usgs_sites(self, siteid):
    properties = None
    try:
      usgs_site_recs = db.session.query(usgs_sites)\
      .filter(usgs_sites.sample_site_id == siteid)\
      .all()
      for rec in usgs_site_recs:
        if properties is None:
          properties = {}
        if rec.usgs_site_id not in properties:
          properties[rec.usgs_site_id] = {}
        properties = {
          'site_id': rec.usgs_site_id,
          'parameters_to_query': rec.parameters_to_query
        }
    except Exception as e:
      current_app.logger.exception(e)
    return properties

  def get(self, sitename=None, site=None):
    start_time = time.time()
    current_app.logger.debug('IP: %s SiteDataAPI get for %s site: %s' % (request.remote_addr, sitename, site))
    ret_code = 404
    results = {}

    try:
      if self.is_valid_project_area(sitename):
        try:
          site_rec = db.session.query(Sample_Site) \
            .join(Project_Area, Project_Area.id == Sample_Site.project_site_id) \
            .join(Site_Type, Site_Type.id == Sample_Site.site_type_id) \
            .filter(Sample_Site.site_name == site)\
            .filter(Project_Area.area_name == sitename).all()
        except exc.SQLAlchemyError as e:
          ret_code = 404
          results = build_json_error(404, f"Site: {site} does not exist.")
        except Exception as e:
          current_app.logger.exception(e)
          ret_code = 501
          results = build_json_error(501, 'Server encountered a problem with the query.')
        else:
          if len(site_rec) > 1:
            current_app.logger.error(f"Multiple records for site: {site} returned.")
          site_rec = site_rec[0]
          if site_rec.site_type.name is not None:
            site_type = site_rec.site_type.name
          else:
            site_type = 'Water Quality'
          # All sites will have some base properties.
          properties = {
            'description': site_rec.description,
            'site_type': site_type,
            'site_name': site_rec.site_name,
            'city': site_rec.city,
            'post_code': site_rec.post_code,
            'state_code': site_rec.state_abbreviation,
            'county': site_rec.county
          }
          if self.return_wq_limits:
            limits = self.get_advisory_limits(sitename)
            if limits is not None:
              properties['advisory_info'] = {}
              properties['advisory_info']['limits'] = limits

          # We set the project info once.
          if self.return_project_area:
            properties['project_area'] = {
              'name': site_rec.project_site.display_name,
              'message': ''
            }
            area_message = self.get_area_message(sitename)
            if area_message is not None:
              results['project_area']['message'] = area_message.message
          if self.get_usgs_properties:
            # Check to see if the site will be adding any USGS obs onto the station page.
            usgs_properties = self.get_usgs_sites(site_rec.id)
            if usgs_properties is not None:
              if 'site_observations' not in properties:
                properties['site_observations'] = {}
              properties['site_observations']['usgs_sites'] = usgs_properties

          ret_code = 200

          site_data = NormalizedSiteData()
          request_data = site_data.get_site_data(sitename, site_rec, self._start_date_obj, self._end_date_obj)
          if request_data is not None:
            properties[site_rec.site_type.name] = {'timeseries': request_data['timeseries'],
                                                   'dataset_start_date': request_data['dataset_start_date'],
                                                   'dataset_end_date': request_data['dataset_end_date']}
          else:
            properties[site_rec.site_type.name] = {}
          site_feature = geojson.Feature(id=site_rec.site_name,
                                    geometry=geojson.Point((site_rec.longitude, site_rec.latitude)),
                                    properties=properties)

          results = site_feature
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


class NormalizedSiteData:
  def load_data_file(self, filename):
    current_app.logger.debug("load_data_file Started.")

    try:
      current_app.logger.debug("Opening file: %s" % (filename))
      with open(filename, 'r') as data_file:
        return json.load(data_file)

    except (IOError, Exception) as e:
      current_app.logger.exception(e)
    return None

  def get_requested_station_data(self, site_rec, start_date_obj, end_date_obj, station_directory, convert_to):
    start_time = time.time()
    current_app.logger.debug("get_requested_station_data Station: %s Start Date: %s End Date: %s"\
                             % (site_rec.site_name, start_date_obj, end_date_obj))

    results = []
    dataset_date_range = []
    try:
      filepath = os.path.join(station_directory, '%s.json' % (site_rec.site_name))
      current_app.logger.debug("Opening station file: %s" % (filepath))

      with open(filepath, "r") as json_data_file:
        stationJson = geojson.load(json_data_file)

        if site_rec.site_type.name == 'Water Quality' and convert_to == 'json-timeseries':

          advisoryList = stationJson['properties']['test']['beachadvisories']
          #Get the date range of data we cover.
          dataset_date_range.append(advisoryList[0]['date'])
          dataset_date_range.append(advisoryList[-1]['date'])

          #If no start/end date times given, we'll return latest results.
          if start_date_obj is None and end_date_obj is None:
            start_date_obj = end_date_obj = dateparser.parse(advisoryList[-1]['date'])
          data_ts = TimeSeries(identifier='enterococcus',
                               name='enterococcus',
                               units='CFU/100mL',
                               data_type='NUMBER')
          results.append(data_ts)
          for ndx in range(len(advisoryList)):
            try:
              tst_date_obj = dateparser.parse(advisoryList[ndx]['date'])
            except ValueError as e:
              current_app.logger.exception(e)
              tst_date_obj = None

            if tst_date_obj is not None and (start_date_obj <= tst_date_obj <= end_date_obj):
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
              ts_rec = TsRecord(**{'timestamp': tst_date_obj,
                                   'value': value})
              data_ts.insert(ts_rec)

        else:
          json_data = json.dumps(stationJson['properties'])
          #Get the date range of data we cover.
          dataset_date_range.append(stationJson['properties']['header']['startTime'])
          dataset_date_range.append(stationJson['properties']['header']['endTime'])

          ts_doc = JtsDocument.fromJSON(json_data)
          #Get the most current record if start and end not provided.
          if start_date_obj is None and end_date_obj is None:
            for series in ts_doc.series:
              latest_rec_datetime = series.records[-1].timestamp
              start_date_obj = end_date_obj = latest_rec_datetime

          #Loop through getting the records that fall within the time frame.
          for series in ts_doc.series:
            matching_recs = []
            for rec in series.records:
              if start_date_obj <= rec.timestamp <= end_date_obj:
                matching_recs.append(rec)
            if len(matching_recs):
              results.append(TimeSeries(identifier=series.identifier,
                                        name=series.name,
                                        data_type=series.data_type,
                                        units=series.units,
                                        records=matching_recs))

      return results, dataset_date_range
    except (IOError, ValueError, Exception) as e:
      current_app.logger.exception(e)

    return None


  def convert_nowcast_data(self, sitename: str, site_rec: Sample_Site, convert_to: str):
    '''
    This site takes the current jsonfile format to a json-timeseries to try and unify the output json records.
    :param sitename:
    :param site_rec:
    :return:
    '''

    prediction_data = self.load_data_file(SITES_CONFIG[sitename]['prediction_file'])
    if prediction_data is not None:
      if convert_to == 'json-timeseries':
        site = site_rec.site_name
        prediction_sites = prediction_data['contents']['stationData']['features']
        # Find if the site has a prediction
        ndx = locate_element(prediction_sites, lambda wq_site: wq_site['properties']['station'] == site)
        if ndx != -1:
          try:
            data_timeout = SITE_TYPE_DATA_VALID_TIMEOUTS['Nowcast']
            nowcast_ts = TimeSeries(identifier='nowcast',
                                    name='nowcast',
                                    data_type='TEXT')
            prediction_date = dateparser.parse(prediction_data['contents']['run_date'])
            nowcast_rec = TsRecord(**{'timestamp': prediction_date,
                                   'value': prediction_sites[ndx]['properties']['ensemble']})
            nowcast_ts.insert(nowcast_rec)

            #jts_document.addSeries(nowcast_ts)
            return nowcast_ts
          except Exception as e:
            current_app.logger.exception(e)
    return None
  def get_site_data(self, sitename: str, site_rec: Sample_Site, start_date: datetime, end_date: datetime):
    site_type = site_rec.site_type.name
    data = None
    jts_document = JtsDocument()

    if site_type == "Water Quality":
      nowcast_data_ts = self.convert_nowcast_data(sitename, site_rec, 'json-timeseries')
      jts_document.addSeries(nowcast_data_ts)

      site_data_ts, dataset_data_range = self.get_requested_station_data(site_rec,
                                                  start_date,
                                                  end_date,
                                                  SITES_CONFIG[sitename]['stations_directory'],
                                                  'json-timeseries')
      jts_document.addSeries(site_data_ts)

    else:
      site_data_ts, dataset_data_range = self.get_requested_station_data(site_rec,
                                                     start_date,
                                                     end_date,
                                                     SITES_CONFIG[sitename]['stations_directory'],
                                                     'json-timeseries')
    if len(site_data_ts):
      jts_document.addSeries(site_data_ts)
      data = { 'timeseries' : jts_document.toJSON(),
                'dataset_start_date': dataset_data_range[0],
                'dataset_end_date': dataset_data_range[1]}


    return data

  def load_data_from_file(self, sitename: str, site_rec: Sample_Site, start_date: datetime, end_date: datetime):
    return self.get_site_data(sitename, site_rec, start_date, end_date)



# Custom JSON encoder for SQLAlchemy models
class AlchemyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        return super().default(obj)

def to_json(db_model, exclude_columns=None):
  if exclude_columns is None:
    exclude_columns = []

  data = json.loads(json.dumps(db_model, cls=AlchemyEncoder))
  return {k: v for k, v in data.items() if k not in exclude_columns}

