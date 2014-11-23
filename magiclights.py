#!/Library/Frameworks/Python.framework/Versions/2.7/bin/python

from flask import Flask
from flask.ext import restful
from flask.ext.restful import abort, reqparse, fields, marshal_with, Resource

from flask.globals import _app_ctx_stack, _request_ctx_stack
from werkzeug.urls import url_parse

import serial, os

# http://stackoverflow.com/questions/19631335/reverting-a-url-in-flask-to-the-endpoint-arguments 
def route_from(url, method = None):
    appctx = _app_ctx_stack.top
    reqctx = _request_ctx_stack.top
    if appctx is None:
        raise RuntimeError("Attempted to match a URL without the "
                           "application context being pushed. This has to be "
                           "executed when application context is available.")

    if reqctx is not None:
        url_adapter = reqctx.url_adapter
    else:
        url_adapter = appctx.url_adapter
        if url_adapter is None:
            raise RuntimeError("Application was not able to create a URL "
                               "adapter for request independent URL matching. "
                               "You might be able to fix this by setting "
                               "the SERVER_NAME config variable.")
    parsed_url = url_parse(url)
    if parsed_url.netloc is not "" and parsed_url.netloc != url_adapter.server_name:
        raise NotFound()
    return url_adapter.match(parsed_url.path, method)

def send_serial(send):
    send += "\n"
    app.logger.warning("Sending serial data: " + send)
    if ser:
        ser.write(send)
        app.logger.warning(ser.read(300))
    else:
        app.logger.warning("Serial port unavailable")

def send_serial_colour(fixture_id, colour):
    send = "%i,1,%i,%i,%i" % (fixture_id, colour[0], colour[1], colour[2])
    send_serial(send)

def send_serial_sequence(fixture_id, sequence):
    send = "%i,2,%i" % (fixture_id, len(sequence))
    for s in sequence:
        send += ",%i,%i,%i,%i" % (s[0], s[1], s[2], s[3])
    send_serial(send)

def send_serial_multifade(fixture_id, channels):
    send = "%i,3,%i" % (fixture_id, len(channels))
    for c in channels:
        send += ",%i" % (c["delay"])
        for s in c["sequence"]:
            send += ",%i,%i,%i,%i" % (s[0], s[1], s[2], s[3])
    send_serial(send)

def send_serial_lamp():
    send = "0,4"

app = Flask(__name__, static_url_path="/static/")
api = restful.Api(app)

fixtures = [
    {"fixture_id": 1, "name": "Lightbar", "multifade_capable": False,
        "sequence_id": 0, "colour_id": 0, "multifade_id": 0, "program_id": 0},
    {"fixture_id": 2, "name": "9 segment lamp", "multifade_capable": True,
        "sequence_id": 0, "colour_id": 0, "multifade_id": 0, "program_id": 0},
]

fixture_fields = {
    "name": fields.String,
    "uri": fields.Url("fixture", absolute=True),
    "colour_id": fields.Url("colour", absolute=True),
    "sequence_id": fields.Url("sequence", absolute=True),
    "multifade_id": fields.Url("multifade", absolute=True),
    "multifade_capable": fields.Raw
}

fixture_parser = reqparse.RequestParser()
fixture_parser.add_argument("name", type=str, location="json")
fixture_parser.add_argument("colour_id", 
    # TODO validate that this colour ID exists
    type=lambda t: route_from(t)[1]["colour_id"],
    location="json")
fixture_parser.add_argument("sequence_id", 
    # TODO validate that this sequence ID exists
    type=lambda t: route_from(t)[1]["sequence_id"],
    location="json")
fixture_parser.add_argument("multifade_id", 
    # TODO validate that this multifade ID exists
    type=lambda t: route_from(t)[1]["multifade_id"],
    location="json")
#fixture_parser.add_argument("program_id", 
#    # TODO validate that this program ID exists
#    type=lambda t: route_from(t)[1]["program_id"],
#    default=0,
#    location="json")

colours = [
    {"colour_id": 0, "rgb": (0,0,0)},
    {"colour_id": 1, "rgb": (255,0,0)},
    {"colour_id": 2, "rgb": (0,255,0)},
    {"colour_id": 3, "rgb": (0,0,255)},
    {"colour_id": 4, "rgb": (255,255,0)},
    {"colour_id": 5, "rgb": (0,255,255)},
    {"colour_id": 6, "rgb": (255,0,255)},
    {"colour_id": 7, "rgb": (255,255,255)},
    {"colour_id": 8, "rgb": (128,255,255)},
    {"colour_id": 9, "rgb": (255,128,255)},
    {"colour_id": 10, "rgb": (255,255,128)},
    {"colour_id": 11, "rgb": (128,128,255)},
    {"colour_id": 12, "rgb": (255,128,128)},
    {"colour_id": 13, "rgb": (128,255,128)},
]

colour_fields = {
    "rgb": fields.Raw,
    "uri": fields.Url("colour", absolute=True),
}

sequences = [
    {"sequence_id": 0, "sequence": [(0,0,0,1000)]}, # Null/off sequence (default)
    {"sequence_id": 1, "sequence": [(255,255,0,60000),(255,0,0,60000)]},
    {"sequence_id": 2, "sequence": [(255,0,0,60000),(255,0,255,60000)]},
    {"sequence_id": 3, "sequence": [(0,255,0,60000),(0,0,255,60000)]},
    {"sequence_id": 4, "sequence": [(255,0,0,60000),(0,255,0,60000),(0,0,255,60000)]},
    {"sequence_id": 5, "sequence": [(0,255,255,60000),(0,255,0,60000),(0,0,255,60000)]},
    {"sequence_id": 6, "sequence": [(255,255,0,60000),(0,255,255,60000),(255,0,255,60000)]},
    #{"sequence_id": 7, "sequence": [(255,0,0,1000)]},
    #{"sequence_id": 8, "sequence": [(0,255,0,1000)]},
    #{"sequence_id": 9, "sequence": [(0,0,255,1000)]},
    #{"sequence_id": 10, "sequence": [(255,255,0,1000)]},
    #{"sequence_id": 11, "sequence": [(0,255,255,1000)]},
    #{"sequence_id": 12, "sequence": [(255,0,255,1000)]},
]

sequence_fields = {
    "sequence": fields.Raw,
    "uri": fields.Url("sequence", absolute=True),
}

multifades = [
    {"multifade_id": 1, "channels": [   # Null/off sequence (default)
        {"delay":     0, "sequence": [(0,0,0,1000)]},
        {"delay":     0, "sequence": [(0,0,0,1000)]},
        {"delay":     0, "sequence": [(0,0,0,1000)]},
        {"delay":     0, "sequence": [(0,0,0,1000)]},
        {"delay":     0, "sequence": [(0,0,0,1000)]},
        {"delay":     0, "sequence": [(0,0,0,1000)]},
        {"delay":     0, "sequence": [(0,0,0,1000)]},
        {"delay":     0, "sequence": [(0,0,0,1000)]},
        {"delay":     0, "sequence": [(0,0,0,1000)]}]},
    {"multifade_id": 1, "channels": [
        {"delay":     0, "sequence": [(255,0,0,5000),(0,0,255,5000)]},
        {"delay":  2500, "sequence": [(255,0,0,5000),(0,0,255,5000)]},
        {"delay":  5000, "sequence": [(255,0,0,5000),(0,0,255,5000)]},
        {"delay":  7500, "sequence": [(255,0,0,5000),(0,0,255,5000)]},
        {"delay": 10000, "sequence": [(255,0,0,5000),(0,0,255,5000)]},
        {"delay": 12500, "sequence": [(255,0,0,5000),(0,0,255,5000)]},
        {"delay": 15000, "sequence": [(255,0,0,5000),(0,0,255,5000)]},
        {"delay": 17500, "sequence": [(255,0,0,5000),(0,0,255,5000)]},
        {"delay": 20000, "sequence": [(255,0,0,5000),(0,0,255,5000)]}]},
    {"multifade_id": 2, "channels": [
        {"delay":  2500, "sequence": [(255,0,0,5000),(255,255,0,5000)]},
        {"delay":  5000, "sequence": [(255,0,0,5000),(255,255,0,5000)]},
        {"delay":  7500, "sequence": [(255,0,0,5000),(255,255,0,5000)]},
        {"delay":     0, "sequence": [(255,0,0,5000),(255,255,0,5000)]},
        {"delay":  2500, "sequence": [(255,0,0,5000),(255,255,0,5000)]},
        {"delay":  5000, "sequence": [(255,0,0,5000),(255,255,0,5000)]},
        {"delay":  7500, "sequence": [(255,0,0,5000),(255,255,0,5000)]},
        {"delay":     0, "sequence": [(255,0,0,5000),(255,255,0,5000)]},
        {"delay":  2500, "sequence": [(255,0,0,5000),(255,255,0,5000)]}]},
    {"multifade_id": 3, "channels": [
        {"delay":     0, "sequence": [(0,255,0,20000),(0,255,0,5000),(0,0,255,5000)]},
        {"delay": 10000, "sequence": [(0,255,0,20000),(0,255,0,5000),(0,0,255,5000)]},
        {"delay":     0, "sequence": [(0,255,0,20000),(0,255,0,5000),(0,0,255,5000)]},
        {"delay": 20000, "sequence": [(0,255,0,20000),(0,255,0,5000),(0,0,255,5000)]},
        {"delay":     0, "sequence": [(0,255,0,20000),(0,255,0,5000),(0,0,255,5000)]},
        {"delay": 10000, "sequence": [(0,255,0,20000),(0,255,0,5000),(0,0,255,5000)]},
        {"delay": 15000, "sequence": [(0,255,0,20000),(0,255,0,5000),(0,0,255,5000)]},
        {"delay":  7000, "sequence": [(0,255,0,20000),(0,255,0,5000),(0,0,255,5000)]},
        {"delay":     0, "sequence": [(0,255,0,20000),(0,255,0,5000),(0,0,255,5000)]}]},
]

multifade_fields = {
    "channels": fields.Raw,
    "uri": fields.Url("multifade", absolute=True),
}

class FixtureListAPI(Resource):
    @marshal_with(fixture_fields)
    def get(self):
        return fixtures

    def post(self):
        pass

class FixtureAPI(Resource):
    @marshal_with(fixture_fields)
    def get(self, fixture_id):
        matches = filter(lambda t: t["fixture_id"] == fixture_id, fixtures)
        if len(matches) == 0:
            abort(404)
        return matches[0]

    @marshal_with(fixture_fields)
    def put(self, fixture_id):
        parsed_args = fixture_parser.parse_args()
        matches = filter(lambda t: t["fixture_id"] == fixture_id, fixtures)
        app.logger.warning(parsed_args)
        if len(matches) == 0:
            abort(404)
        fixture = matches[0];

        if "name" in parsed_args:
            fixture["name"] = parsed_args["name"]

        # Request should specify one of colour_id, sequence_id, multifade_id, program_id
        # Whichever one is specified becomes the new program for this fixture
        # Check if fixture supports multifade, if not and multifade_id set then error
        # Set all ID values to zero except the one specified
        # Trigger corresponding serial send sequence
        if "colour_id" in parsed_args and parsed_args["colour_id"] is not None:
            matches = filter(lambda t: t["colour_id"] == parsed_args["colour_id"], colours)
            if len(matches) == 0:
                abort(400, message="colour_id '%i' not found" % (parsed_args["colour_id"]))
            fixture["colour_id"] = parsed_args["colour_id"]
            send_serial_colour(fixture_id, matches[0]["rgb"])
        if "sequence_id" in parsed_args and parsed_args["sequence_id"] is not None:
            matches = filter(lambda t: t["sequence_id"] == parsed_args["sequence_id"], sequences)
            if len(matches) == 0:
                abort(400, message="sequence_id '%i' not found" % (parsed_args["sequence_id"]))
            fixture["sequence_id"] = parsed_args["sequence_id"]
            send_serial_sequence(fixture_id, matches[0]["sequence"])
        if "multifade_id" in parsed_args and parsed_args["multifade_id"] is not None:
            if not fixture["multifade_capable"]:
                abort(400, message="multifade_id set but fixture with id: %i is not multifade capable" % (fixture["fixture_id"]))
            matches = filter(lambda t: t["multifade_id"] == parsed_args["multifade_id"], multifades)
            if len(matches) == 0:
                abort(400, message="multifade_id '%i' not found" % (parsed_args["multifade_id"]))
            fixture["multifade_id"] = parsed_args["multifade_id"]
            send_serial_multifade(fixture_id, matches[0]["channels"])
        #if "program_id" in parsed_args:
        #    # TODO - check valid program id
        #    fixture["program_id"] = parsed_args["program_id"]

        app.logger.warning(fixtures)
        # TODO should trigger serial module to send command with new sequence
        #      (not if only changing the name however)
        return fixture, 201

    def delete(self, fixture_id):
        pass

class ColourListAPI(Resource):
    @marshal_with(colour_fields)
    def get(self):
        return colours[1:];

    def post(self):
        pass

class ColourAPI(Resource):
    @marshal_with(colour_fields)
    def get(self, colour_id):
        matches = filter(lambda t: t["colour_id"] == colour_id, colours)
        if len(matches) == 0:
            abort(404)
        return matches[0]

    def put(self, colour_id):
        pass

    def delete(self, colour_id):
        pass

class SequenceListAPI(Resource):
    @marshal_with(sequence_fields)
    def get(self):
        return sequences[1:];

    def post(self):
        pass

class SequenceAPI(Resource):
    @marshal_with(sequence_fields)
    def get(self, sequence_id):
        matches = filter(lambda t: t["sequence_id"] == sequence_id, sequences)
        if len(matches) == 0:
            abort(404)
        return matches[0]

    def put(self, sequence_id):
        pass

    def delete(self, sequence_id):
        pass

class MultiFadeListAPI(Resource):
    @marshal_with(multifade_fields)
    def get(self):
        return multifades[1:];

    def post(self):
        pass

class MultiFadeAPI(Resource):
    @marshal_with(multifade_fields)
    def get(self, multifade_id):
        matches = filter(lambda t: t["multifade_id"] == multifade_id, multifades)
        if len(matches) == 0:
            abort(404)
        return matches[0]

    def put(self, multifade_id):
        pass

    def delete(self, multifade_id):
        pass

api.add_resource(FixtureListAPI, "/magiclights/api/fixtures", endpoint = "fixtures")
api.add_resource(FixtureAPI, "/magiclights/api/fixtures/<int:fixture_id>", endpoint = "fixture")
api.add_resource(ColourListAPI, "/magiclights/api/colours", endpoint = "colours")
api.add_resource(ColourAPI, "/magiclights/api/colours/<int:colour_id>", endpoint = "colour")
api.add_resource(SequenceListAPI, "/magiclights/api/sequences", endpoint = "sequences")
api.add_resource(SequenceAPI, "/magiclights/api/sequences/<int:sequence_id>", endpoint = "sequence")
api.add_resource(MultiFadeListAPI, "/magiclights/api/multifades", endpoint = "multifades")
api.add_resource(MultiFadeAPI, "/magiclights/api/multifades/<int:multifade_id>", endpoint = "multifade")

@app.route("/")
def root():
    return app.send_static_file("index.html")
@app.route("/style.css")
def style():
    return app.send_static_file("style.css")

if __name__ == "__main__":
    try:
        ser = serial.Serial(os.environ["SERIAL"], 9600, timeout=1)
        print "Serial connection open"
    except:
        ser = False
        print "Unable to open serial connection!"

    if os.environ.get("DEBUG") is None:
        app.run(host=os.environ["HOST"], port=int(os.environ["PORT"]))
    else:
        app.run(debug=True)



