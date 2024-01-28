import os
from dash.exceptions import PreventUpdate
import numpy as np
import json
import pandas as pd
import geopandas as gpd
from dash import Input, Output, dcc, html, Dash
import dash_leaflet as dl
import dash_bootstrap_components as dbc
import dash_vtk
from dash_vtk.utils import to_mesh_state, to_volume_state
import vtk
from terracotta_toolbelt import singleband_url
import vtk.util.numpy_support as vnp

crs = "EPSG:28415"
wgs_crs = "EPSG:4326"
root_dir = os.path.join("data", "raspad")
input_dir = os.path.join(root_dir, "inputs")
output_dir = os.path.join(root_dir, "outputs")
vector_out_dir = os.path.join(output_dir, "vector")
vector_in_dir = os.path.join(input_dir, "vector")
raster_in_dir = os.path.join(input_dir, "raster")
border = gpd.read_file(os.path.join(vector_in_dir, "border.shp"), crs=crs)
border_wgs = border.to_crs(wgs_crs)

grid = gpd.read_file(os.path.join(vector_out_dir, "data.shp"), crs=crs)
grid.crs = border.crs
grid_wgs = grid.to_crs(wgs_crs)

streams_l = gpd.read_file(os.path.join(vector_in_dir, "stream_left.shp"), crs=crs)
streams_l_wgs = streams_l.to_crs(wgs_crs)
streams_r = gpd.read_file(os.path.join(vector_in_dir, "stream_right.shp"), crs=crs)
streams_r_wgs = streams_r.to_crs(wgs_crs)
streams = gpd.GeoDataFrame(pd.concat([streams_l_wgs, streams_r_wgs], ignore_index=True))

quarry = gpd.read_file(os.path.join(vector_in_dir, "quarry_osm_poly.shp"), crs=crs)
quarry_wgs = quarry.to_crs(wgs_crs)

SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "16rem",
    "padding": "2rem 1rem",
    "background-color": "#f8f9fa",
}

# the styles for the main content position it to the right of the sidebar and
# add some padding.
CONTENT_STYLE = {
    "margin-left": "18rem",
    "margin-right": "2rem",
    "padding": "2rem 1rem",
}
sidebar = html.Div(
    [
        html.H6("Распадская", className="display-6"),
        html.Hr(),
        dbc.Nav(
            [
                dbc.NavLink("Концептуальная модель", href="/", active="exact"),
                dbc.NavLink("Геофильтрационная модель", href="/geof-model", active="exact"),
                dbc.NavLink("Результаты", href="/results", active="exact"),
            ],
            vertical=True,
            pills=True,
        ),
    ],
    style=SIDEBAR_STYLE,
)
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
content = html.Div(id="page-content", style=CONTENT_STYLE)
app.layout = html.Div([dcc.Location(id="url"), sidebar, content])

image_bounds = [[40.712216, -74.22655], [40.773941, -74.12544]]
concept_model = html.Div(
    dl.Map(center=[border_wgs.centroid.y[0], border_wgs.centroid.x[0]], attributionControl=False, zoom=11, children=[
        dl.TileLayer(),
        dl.TileLayer(id="tc", url="http://localhost:5000/singleband/dem/ELEV/{z}/{x}/{y}.png?colormap=viridis&stretch_range=[268,506]", opacity=0.7),
        dl.Colorbar(id="cbar", colorscale="viridis", width=150, height=20, style={"margin-left": "40px"}, position="bottomleft", min=268, max=506),
        dl.LayersControl(
            [
                dl.Overlay(
                    dl.LayerGroup(
                        dl.GeoJSON(
                            data=json.loads(border_wgs.to_json()),
                            style={"color": "red", "fillColor": "none"})
                    ),
                    name="Граница модели", checked=True),
                dl.Overlay(
                    dl.LayerGroup(
                        dl.GeoJSON(
                            data=json.loads(streams.to_json())
                        )
                    ),
                    name="Ручьи",
                    checked=True),
                dl.Overlay(
                    dl.LayerGroup(
                        dl.GeoJSON(
                            data=json.loads(quarry_wgs.to_json()),
                            style={"color": "#FFEDA0", "fillColor": ""},
                        )
                    ),
                    name="Карьеры, отработанные до 2009г.",
                    checked=True),
            ],
        ),
    ], style={'height': '80vh'}),
)

filename = os.path.join(root_dir, "data_000000.vtk")

reader = vtk.vtkUnstructuredGridReader()
reader.SetFileName(filename)
reader.Update()
dataset = reader.GetOutput()
# Get the cell data
cell_data = dataset.GetCellData()
array_index = cell_data.GetArray('riv_0_cond')

# Find cells with NaN values
nan_cells = []
for cell_id in range(dataset.GetNumberOfCells()):
    if vtk.vtkMath.IsNan(array_index.GetTuple1(cell_id)):
        nan_cells.append(cell_id)

# Create an array to mark cells for removal
remove_array = vtk.vtkCharArray()
remove_array.SetNumberOfComponents(1)
remove_array.SetNumberOfTuples(dataset.GetNumberOfCells())
remove_array.Fill(0)

for cell_id in nan_cells:
    remove_array.SetValue(cell_id, '1')

# Create a threshold filter to remove cells marked for removal
threshold = vtk.vtkThreshold()
threshold.SetInputData(dataset)
threshold.SetInputArrayToProcess(0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS, 'riv_0_cond')
threshold.Update()

# Get the output after removing cells
filtered_dataset = threshold.GetOutput()

mesh_state = to_mesh_state(filtered_dataset, field_to_keep="riv_0_cond")
mesh_state2 = to_mesh_state(dataset, field_to_keep="k")
geof_model = html.Div(
    style={"width": "100%", "height": "calc(100vh - 15px)"},
    children=[dash_vtk.View([
        dash_vtk.GeometryRepresentation([
            dash_vtk.Mesh(state=mesh_state2),
        ]),
        dash_vtk.GeometryRepresentation([
            dash_vtk.Mesh(state=mesh_state),
        ])
    ])
    ])

@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def render_page_content(pathname):
    if pathname == "/":
        return concept_model
    elif pathname == "/geof-model":
        return geof_model
    elif pathname == "/results":
        return geof_model
    # If the user tries to reach a different page, return a 404 message
    return html.Div(
        [
            html.H1("404: Not found", className="text-danger"),
            html.Hr(),
            html.P(f"The pathname {pathname} was not recognised..."),
        ],
        className="p-3 bg-light rounded-3",
    )


if __name__ == '__main__':
    app.run(debug=True)
