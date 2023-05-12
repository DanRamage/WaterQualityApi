"""
To use the command line interface you have to:
Load the python venv(source /path/to/python/venv/bin/activate
export FLASK_APP=<fullpathto>/manage.py
"""
import sys
sys.path.append('../commonfiles/python')
import os
import click
from flask import Flask, current_app, redirect, url_for, request
import logging.config
from logging.handlers import RotatingFileHandler
from logging import Formatter
import time
from app import db
from config import *
from .wq_models import Project_Area, Sample_Site, Boundary, Site_Extent, Sample_Site_Data, Site_Type, BeachAmbassador
from datetime import datetime
import json
import requests
import shapely
from shapely.wkb import loads as wkb_loads
from shapely.geometry import Point, Polygon, box

#from sqlalchemy import MetaData
#from sqlalchemy import create_engine
#from sqlalchemy.orm import sessionmaker

#import mysql.connector
#from mysql.connector.constants import ClientFlag

app = Flask(__name__)
db.app = app
db.init_app(app)
# Create in-memory database
app.config['DATABASE_FILE'] = DATABASE_FILE
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_ECHO'] = SQLALCHEMY_ECHO

def init_logging(app):
  app.logger.setLevel(logging.DEBUG)
  file_handler = RotatingFileHandler(filename = LOGFILE)
  file_handler.setLevel(logging.DEBUG)
  file_handler.setFormatter(Formatter('%(asctime)s,%(levelname)s,%(module)s,%(funcName)s,%(lineno)d,%(message)s'))
  app.logger.addHandler(file_handler)

  app.logger.debug("Logging initialized")

  return



@app.cli.command('build_sites')
@click.option('--params', nargs=2)
def build_sites(params):
  start_time = time.time()
  init_logging(app)
  site_name = params[0]
  output_file = params[1]
  current_app.logger.debug("build_sites started Site: %s Outfile: %s" % (site_name, output_file))
  try:
    #.join(Boundary, Sample_Site.boundaries) \
      sample_sites = db.session.query(Sample_Site) \
      .join(Project_Area, Project_Area.id == Sample_Site.project_site_id) \
      .filter(Project_Area.area_name == site_name).all()
  except Exception as e:
    current_app.logger.exception(e)
  else:
    try:
      with open(output_file, "w") as sample_site_file:
        #Write header
        row = 'WKT,EPAbeachID,SPLocation,Description,County,Boundary,ExtentsWKT\n'
        sample_site_file.write(row)
        for site in sample_sites:
          boundaries = []
          for boundary in site.boundaries:
            boundaries.append(boundary.boundary_name)
          wkt_location = "POINT(%f %f)" % (site.longitude, site.latitude)
          site_extents = site.extents
          wkt_extent = ""
          for extent in site_extents:
            wkt_extent = extent.wkt_extent
          row = '\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\"\n' % (wkt_location,
                                       site.epa_id,
                                       site.site_name,
                                       site.description,
                                       site.county,
                                       ",".join(boundaries),
                                       wkt_extent)
          sample_site_file.write(row)

    except (IOError, Exception) as e:
      current_app.logger.exception(e)

  current_app.logger.debug("build_sites finished in %f seconds" % (time.time()-start_time))

@app.cli.command()
@click.option('--params', nargs=2)
def build_boundaries(params):
  start_time = time.time()
  init_logging(app)
  site_name = params[0]
  output_file = params[1]
  current_app.logger.debug("build_boundaries started. Site: %s Outfile: %s" % (site_name, output_file))
  try:
    boundaries = db.session.query(Boundary) \
      .join(Project_Area, Project_Area.id == Boundary.project_site_id) \
      .filter(Project_Area.area_name == site_name).all()
  except Exception as e:
    current_app.logger.exception(e)
  else:
    try:
      with open(output_file, "w") as boundary_file:
        #Write header
        row = 'WKT,Name\n'
        boundary_file.write(row)
        for boundary in boundaries:
          #Construct the boundary geometry object from the well known binary.
          boundary_geom = wkb_loads(boundary.wkb_boundary)
          row = '\"%s\",\"%s\"\n' % (boundary_geom.wkt,
                                     boundary.boundary_name)
          boundary_file.write(row)

    except (IOError, Exception) as e:
      current_app.logger.exception(e)

  current_app.logger.debug("build_boundaries finished in %f seconds" % (time.time()-start_time))

#import_sample_sites --params sarasota /Users/danramage/Documents/workspace/WaterQuality/Florida_Water_Quality/config/sample_sites_boundary.csv /Users/danramage/Documents/workspace/WaterQuality/Florida_Water_Quality/config/sarasota_boundaries.csv
#Given the project name, the sample site csv and boundary csv, this populates the sample_site and boudnary tables.
@app.cli.command()
@click.option('--params', nargs=3)
def import_sample_sites(params):
  start_time = time.time()
  init_logging(app)
  area_name = params[0]
  sample_site_csv = params[1]
  boundaries_file = params[2]
  current_app.logger.debug("import_sample_sites started.")

  wq_sites = wq_sample_sites()
  wq_sites.load_sites(file_name=sample_site_csv, boundary_file=boundaries_file)

  row_entry_date = datetime.now()

  area_rec = db.session.query(Project_Area)\
    .filter(Project_Area.area_name == area_name).first()
  #ADd the boundaries first
  for site in wq_sites:
    for contained_by in site.contained_by:
      try:
        bound = Boundary()
        bound.row_entry_date = row_entry_date.strftime('%Y-%m-%d %H:%M:%S')
        bound.project_site_id = area_rec.id
        bound.boundary_name = contained_by.name
        bound.wkb_boundary = contained_by.object_geometry.wkb
        bound.wkt_boundary = contained_by.object_geometry.to_wkt()
        current_app.logger.debug("Adding boundary: %s" % (bound.boundary_name))
        db.session.add(bound)
        db.session.commit()
      except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()

  for site in wq_sites:
    try:
      site_rec = Sample_Site()
      site_rec.project_site_id = area_rec.id
      site_rec.row_entry_date = row_entry_date.strftime('%Y-%m-%d %H:%M:%S')
      site_rec.site_name = site.name
      site_rec.description = site.description
      site_rec.county = site.county
      site_rec.longitude = site.object_geometry.x
      site_rec.latitude = site.object_geometry.y
      site_rec.wkt_location = site.object_geometry.wkt
      site_rec.temporary_site = False
      #Look up boundaries
      for contained_by in site.contained_by:
        boundary_rec = db.session.query(Boundary)\
          .filter(Boundary.boundary_name == contained_by.name).first()
        site_rec.boundaries.append(boundary_rec)
      current_app.logger.debug("Adding site: %s" % (site_rec.site_name))
      db.session.add(site_rec)
      db.session.commit()
    except Exception as e:
      current_app.logger.exception(e)
      db.session.rollback()


  current_app.logger.debug("import_sample_sites finished in %f seconds" % (time.time()-start_time))


#import_sample_sites --params sarasota /Users/danramage/Documents/workspace/WaterQuality/Florida_Water_Quality/config/sample_sites_boundary.csv /Users/danramage/Documents/workspace/WaterQuality/Florida_Water_Quality/config/sarasota_boundaries.csv
#Given the project name, the sample site csv and boundary csv, this populates the sample_site and boudnary tables.
@app.cli.command()
@click.option('--params', nargs=2)
def import_sample_data(params):
  start_time = time.time()
  init_logging(app)
  area_name = params[0]
  sample_sites_data_directory = params[1]
  current_app.logger.debug("import_sample_data started.")

  try:
    row_entry_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sample_sites = db.session.query(Sample_Site) \
      .join(Project_Area, Project_Area.id == Sample_Site.project_site_id) \
      .filter(Project_Area.area_name == area_name).all()
    for site in sample_sites:
      sample_site_data_file = os.path.join(sample_sites_data_directory, "%s.json" % (site.site_name.upper()))
      current_app.logger.debug("Opening file: %s" % (sample_site_data_file))
      try:
        with open(sample_site_data_file, 'r') as data_file:
          sample_data = json.load(data_file)
          props = sample_data['properties']
          results_data = props['test']['beachadvisories']
          for result in results_data:
            try:
              sample_data_rec = Sample_Site_Data(row_entry_date=row_entry_date,
                                             sample_date=result['date'],
                                             sample_value=float(result['value']),
                                             site_id=site.id)
              db.session.add(sample_data_rec)
              db.session.commit()
            except Exception as e:
              current_app.logger.exception(e)
              db.session.rollback()
      except(IOError, Exception) as e:
        current_app.logger.exception(e)
  except (Exception, IOError) as e:
    current_app.logger.exception(e)

  current_app.logger.debug("import_sample_data finished in %f seconds." % (time.time() - start_time))


#reverse_geocode_sites --params results_file
#This will loop through all the sites and reverse geocode them. This is useful so we can have the zipcode, city, state info
#for sites.
@app.cli.command('reverse_geocode_sites')
@click.option('--params', nargs=1)
def reverse_geocode_sites(params):
  api_key = '5465cd37823048e9952b31a613539fe5'
  URL = 'https://api.geoapify.com/v1/geocode/reverse?lat={latitude}4&lon={longitude}&api_key={api_key}'
  start_time = time.time()
  init_logging(app)
  results_file = params
  current_app.logger.debug("reverse_geocode_sites started file: %s" % (results_file))
  try:
      sample_sites = db.session.query(Sample_Site) \
        .join(Project_Area, Project_Area.id == Sample_Site.project_site_id)\
        .order_by(Project_Area.area_name)\
        .all()
  except Exception as e:
    current_app.logger.exception(e)
  else:
    try:
      with open(results_file, "w") as geocode_file:
        geo_data = []
        state = None
        previous_postcode = None
        for site in sample_sites:
          current_app.logger.debug("Reverse Geocode query for site: {site_name}".format(site_name=site.site_name))
          try:
            url = URL.format(latitude=site.latitude, longitude=site.longitude, api_key=api_key)
            req = requests.get(url)
            if req.status_code == 200:
              geocode = req.json()
              geo_data.append(geocode)
              site.state_abbreviation = geocode['features'][0]['properties']['state_code']
              site.county = geocode['features'][0]['properties']['county']
              site.city = geocode['features'][0]['properties']['city']
              if 'postcode' in geocode['features'][0]['properties']:
                site.post_code = geocode['features'][0]['properties']['postcode']
                previous_postcode = site.post_code
              else:
                if state == site.state_abbreviation:
                  current_app.logger.error("Postcode not available, using previous.")
                  site.post_code = previous_postcode
                else:
                  current_app.logger.error("Postcode not available, unable to set.")

              state = site.state_abbreviation
              db.session.commit()
            else:
              current_app.logger.error("Request failed. Code: {req_code} Message: {message}".format(req_code=req.status_code, message=req.text))
          except Exception as e:
            current_app.logger.exception(e)
        json.dump(geo_data, geocode_file)
    except (Exception, IOError) as e:
      current_app.logger.exception(e)


@app.cli.command('get_bcrs_sites')
@click.option('--params', nargs=2)
def get_bcrs_sites(params):
  start_time = time.time()
  location = params[0]
  bbox = params[1]

  ll, ur = bbox.split(',')
  ll = ll.split(' ')
  ur = ur.split(' ')

  init_logging(app)
  results_file = params
  current_app.logger.debug("get_bcrs_sites started.")
  try:
    url = "https://api.visitbeaches.org/graphql"
    params = {
      'operationName': 'GetMappedReports',
      'variables': {
        "bounds": {
          "northEast": {
            "latitude": float(ur[0]),
            "longitude": float(ur[1])
          },
          "southWest": {
            "latitude": float(ll[0]),
            "longitude": float(ll[1])
          }
        },
        "layerId": "2"
      },
      "query": """query GetMappedReports($bounds: BoundsInput!, $layerId: ID!) {\n  beaches(orderBy: [{column: NAME, order: ASC}]) {\n    ...Beach\n    __typename\n  }\n  clusteredLayerReports(layerId: $layerId, bounds: $bounds) {\n    clusters {\n      ...Cluster\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment Beach on Beach {\n  id\n  name\n  website\n  logo\n  latitude\n  longitude\n  amenities {\n    description\n    link\n    __typename\n  }\n  imageAttachments(orderBy: [{column: CREATED_AT, order: DESC}]) {\n    ...ImageAttachment\n    __typename\n  }\n  city {\n    ...City\n    __typename\n  }\n  location\n  __typename\n}\n\nfragment City on City {\n  name\n  latitude\n  longitude\n  county {\n    ...County\n    __typename\n  }\n  state {\n    ...State\n    __typename\n  }\n  __typename\n}\n\nfragment County on County {\n  name\n  latitude\n  longitude\n  state {\n    ...State\n    __typename\n  }\n  __typename\n}\n\nfragment State on State {\n  name\n  abbreviation\n  latitude\n  longitude\n  __typename\n}\n\nfragment ImageAttachment on ImageAttachment {\n  originalUrl\n  previewUrl\n  thumbnailUrl\n  __typename\n}\n\nfragment Cluster on Cluster {\n  key\n  center {\n    latitude\n    longitude\n    __typename\n  }\n  reports {\n    ...Report\n    __typename\n  }\n  __typename\n}\n\nfragment Report on Report {\n  id\n  user {\n    ...User\n    __typename\n  }\n  agree\n  disagree\n  createdAt\n  latitude\n  longitude\n  reportParameters {\n    ...ReportParameter\n    __typename\n  }\n  reportableType\n  reportableId\n  __typename\n}\n\nfragment ReportParameter on ReportParameter {\n  parameter {\n    ...Parameter\n    __typename\n  }\n  parameterValues {\n    ...ParameterValue\n    __typename\n  }\n  value\n  display\n  __typename\n}\n\nfragment Parameter on Parameter {\n  id\n  name\n  icon\n  prompt\n  description\n  type\n  rangeMin\n  rangeMax\n  unit\n  first\n  parameterCategory {\n    ...ParameterCategory\n    __typename\n  }\n  parameterValues {\n    ...ParameterValue\n    __typename\n  }\n  __typename\n}\n\nfragment ParameterCategory on ParameterCategory {\n  id\n  name\n  icon\n  description\n  slug\n  order\n  __typename\n}\n\nfragment ParameterValue on ParameterValue {\n  id\n  name\n  description\n  value\n  imagePath\n  icon\n  __typename\n}\n\nfragment User on User {\n  id\n  name\n  email\n  alert {\n    ...Alert\n    __typename\n  }\n  __typename\n}\n\nfragment Alert on Alert {\n  id\n  uuid\n  email\n  beaches {\n    ...Beach\n    __typename\n  }\n  __typename\n}\n"""
    }

    if url:
      # current_app.logger.debug("IP: %s BCRSQuery querying: %s" % (request.remote_addr, url))
      req = requests.post(url, json=params)
      if req.status_code == 200:
        bbox = box(float(ll[1]), float(ll[0]), float(ur[1]), float(ur[0]))
        proj_area = db.session.query(Project_Area) \
          .filter(Project_Area.area_name == location) \
          .one()
        site_type = db.session.query(Site_Type) \
          .filter(Site_Type.name == 'Beach Ambassador') \
          .one()

        row_entry_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        json_data = req.json()
        for beach in json_data['data']['beaches']:
          #Check if the site exists.
          site_point = Point(beach['longitude'], beach['latitude'])
          if bbox.contains(site_point):
            add_site = False
            try:
              current_app.logger.debug("Station: %s in bbox, checking if it already exists in database." % (beach['name']))

              site_rec = db.session.query(Sample_Site) \
                .filter(Sample_Site.site_name == beach['name'])\
                .filter(Sample_Site.project_site_id == proj_area.id).one()
              current_app.logger.debug("Station: %s already exists in database, not adding." % (beach['name']))
            except Exception as e:
              current_app.logger.debug("Site: %s is not in database." % (beach['name']))
              add_site = True
            if add_site:
              try:
                new_site = Sample_Site(row_entry_date=row_entry_date,
                                       site_name=beach['name'],
                                       description=beach['name'],
                                       latitude=beach['latitude'],
                                       longitude=beach['longitude'],
                                       project_site_id=proj_area[0].id,
                                       site_type_id=site_type[0].id,
                                       city=beach['city']['name'],
                                       county=beach['city']['county']['name'],
                                       state_abbreviation=beach['city']['state']['abbreviation'],
                                       temporary_site=False)
                db.session.add(new_site)
                db.session.commit()
                site_url = "https://visitbeaches.org/beach/{site_id}".format(site_id=beach['id'])
                bcrs_site = BeachAmbassador(row_entry_date=row_entry_date,
                                            bcrs_id=beach['id'],
                                            site_url=site_url,
                                            sample_site_id=new_site.id)
                db.session.add(bcrs_site)
                db.session.commit()
              except Exception as e:
                current_app.logger.exception(e)
  except Exception as e:
    current_app.logger.exception(e)
  return


@app.cli.command('get_shellcast_sites')
@click.option('--params', nargs=4)
def get_shellcast_sites(params):
  #from .ShellcastModels import NCDMFLease
  init_logging(app)
  location = params[0]
  url = params[1]
  bbox = params[2]
  dry_run = params[3] == 'True'
  '''
  Killl devil hills:
  LL: -75.851530, 35.838785
  UR: -75.589265,  36.145002
  
  SC Myrtle Beach:
  URL: https://shellcast-sc-dot-ncsu-shellcast.appspot.com/static/cmu_bounds.geojson
  "33.401803 -79.475394,33.844950 -77.916390" 
  '''
  '''
  user_name = params[0]
  user_pwd = params[1]
  db_ip_addr = params[2]
  database_name = params[3]
  config = {
    'user': user_name,
    'password': user_pwd,
    'host': db_ip_addr,
    'database': db_ip_addr
  }
  '''
  try:
    ll, ur = bbox.split(',')
    ll = ll.split(' ')
    ur = ur.split(' ')
    location_bbox = box(float(ll[1]), float(ll[0]), float(ur[1]), float(ur[0]))

    current_app.logger.debug("Querying url: %s" % (url))
    req = requests.get(url)
    if req.status_code == 200:
      proj_area = db.session.query(Project_Area)\
        .filter(Project_Area.area_name==location)\
        .one()
      site_type = db.session.query(Site_Type)\
        .filter(Site_Type.name == 'Shellcast')\
        .one()

      row_entry_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      json_data = req.json()
      for cmu in json_data['features']:
        geometry = cmu['geometry']
        cmu_poly = None
        if geometry['type'] == 'MultiPolygon':
          cmu_poly = Polygon(geometry['coordinates'][0][0])
        elif geometry['type'] == 'Polygon':
          cmu_poly = Polygon(geometry['coordinates'][0])

        if cmu_poly is not None and cmu_poly.intersects(location_bbox):
          props = cmu['properties']
          cmu_name = ""
          if 'cmu_name' in props:
            cmu_name = props['cmu_name']
          elif 'Label' in props:
            cmu_name = props['Label']
          current_app.logger.debug(f"CMU: {cmu_name} intersects {location} bbox.")
          add_site = False
          try:
            current_app.logger.debug(
              f"Station: {cmu_name} in bbox, checking if it already exists in database.")

            site_rec = db.session.query(Sample_Site) \
              .filter(Sample_Site.site_name == cmu_name) \
              .filter(Sample_Site.project_site_id == proj_area.id).one()
            current_app.logger.debug(f"Station: {cmu_name} already exists in database, not adding.")
          except Exception as e:
            current_app.logger.debug(f"Site: {cmu_name} is not in database.")
            add_site = True
          if add_site:
            center_pt = cmu_poly.centroid.coords[0]
            new_site = Sample_Site(row_entry_date=row_entry_date,
                                   site_name=cmu_name,
                                   description=cmu_name,
                                   latitude=center_pt[1],
                                   longitude=center_pt[0],
                                   project_site_id=proj_area.id,
                                   site_type_id=site_type.id,
                                   city='',
                                   county='',
                                   state_abbreviation='',
                                   temporary_site=False)
            if not dry_run:
              current_app.logger.debug(f"Adding site: {new_site.site_name}")
              db.session.add(new_site)
              db.session.commit()

    else:
      current_app.logger.error("Unable to GET url: %s, status code: %d" % (url, req.status_code))
    '''
    current_app.logger.debug("Connecting to database.")
    #mysql+mysqlconnector://<user>:<password>@<host>[:<port>]/<dbname>
    connect_string = "mysql+mysqlconnector://{user}:{password}@{host}:{port}/{dbname}".format(uesr=user_name,
                                                                                              password=user_pwd,
                                                                                              host=db_ip_addr,
                                                                                              dbname=db_ip_addr)

    dbEngine = create_engine(connect_string)
    # metadata object is used to keep information such as datatypes for our table's columns.
    metadata = MetaData()
    metadata.bind = dbEngine
    Session = sessionmaker(bind=dbEngine)
    session = Session()
    connection = dbEngine.connect()

    #cnxn = mysql.connector.connect(**config)
    '''
  except Exception as e:
    current_app.logger.exception(e)

  return
