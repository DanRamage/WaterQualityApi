import python_jsonschema_objects as pjs
import jsonschema as jsc
import json
SWIMDRINKFISHSCHEMAFILE="swimdrinkfish_schema.json"

def build_class_from_schema(schema_file):
    try:
        with open(schema_file, "r") as schema_obj:
            schema_json = json.load(schema_obj)
            builder = pjs.ObjectBuilder(schema_json)
            schema_class = builder.build_classes()
            return(schema_class.Recml)
    except Exception as e:
        raise e
    return None


class SwimDrinkFish:
    def __init__(self, schema_file):
        return
