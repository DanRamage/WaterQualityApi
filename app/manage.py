"""
To use the command line interface you have to:
Load the python venv(source /path/to/python/venv/bin/activate
export FLASK_APP=<fullpathto>/manage.py
"""
import sys
sys.path.append('../../commonfiles/python')
import os
import click
from flask import Flask, current_app, redirect, url_for, request
import logging.config
from logging.handlers import RotatingFileHandler
from logging import Formatter
import time
from app import db
from config import *
from wq_models import Project_Area, Sample_Site, Boundary, Site_Extent, Sample_Site_Data
from datetime import datetime
from shapely.wkb import loads as wkb_loads
from wq_sites import wq_sample_sites
import json

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



@app.cli.command()
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
