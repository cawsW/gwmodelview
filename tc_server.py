import os
import terracotta as tc
from terracotta import update_settings
from terracotta.server import create_app


DRIVER_PATH = "data/db.sqlite"
GEOTIFF_DIR = os.path.join("data", "raspad", "inputs", "raster")
KEYS = ["gcm", "parameter"]
RASTER_FILES = [
    {
        "key_values": {
            "gcm": "dem",
            "parameter": "ELEV",
        },
        "path": os.path.join("data", "raspad", "inputs", "raster", "dem.tif"),
    },
]


def load(db_name: str, keys, raster_files):
    # get a TerracottaDriver that we can use to interact with
    # the database
    driver = tc.get_driver(db_name)

    # create the database file if it doesn't exist already
    if not os.path.isfile(db_name):
        driver.create(keys)

    # check that the database has the same keys that we want
    # to load
    print(driver.key_names)
    assert list(driver.key_names) == keys, (driver.key_names, keys)

    # connect to the database
    with driver.connect():
        # insert metadata for each raster into the database
        for raster in raster_files:
            driver.insert(raster["key_values"], raster["path"])


if __name__ == '__main__':
    load(DRIVER_PATH, KEYS, RASTER_FILES)
    update_settings(DRIVER_PATH=DRIVER_PATH, REPROJECTION_METHOD="nearest")
    server = create_app()
    # point.register(server)
    server.run(port=5000, host="localhost", threaded=False)